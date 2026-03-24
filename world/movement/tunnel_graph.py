"""
Tunnel routing via networkx.

Replaces the hand-rolled BFS in world/movement/tunnels.py with a cached
networkx DiGraph per tunnel network. The graph is built lazily on first use
and cached in _TUNNEL_GRAPHS keyed by network tag string.

Invalidate the cache whenever tunnel topology changes (room tagged/untagged,
exit added/removed) by calling invalidate_tunnel_graph(network_tag).

Public API:
    find_tunnel_route(start_room, destination_sector) -> list[int] | None
        Returns a list of room IDs (excluding start) from start_room to the
        endpoint room for destination_sector, or None if no route exists.
        Drop-in replacement for the old _find_tunnel_route BFS.

    get_tunnel_graph(network_tag) -> nx.DiGraph
        Returns the cached graph for a tunnel network, building it if needed.

    invalidate_tunnel_graph(network_tag)
        Clears the cached graph so it is rebuilt on next use.

    get_eta_seconds(start_room, destination_sector, speed_class) -> int | None
        Returns estimated travel time in seconds based on path length and
        speed class delays, or None if no route.

    get_valid_destinations(room) -> list[str]
        Returns sector names reachable from this room (same as tunnels.py
        _get_valid_destinations but uses the graph for validation).
"""

import pickle

import networkx as nx
from evennia.objects.objects import DefaultExit
from evennia.utils.search import search_tag

# Module-level in-process cache: {network_tag: nx.DiGraph}
# Graphs are also persisted to diskcache so they survive server reloads.
_TUNNEL_GRAPHS: dict[str, nx.DiGraph] = {}

_CACHE_KEY_PREFIX = "tunnel_graph:"


def _cache_key(network_tag: str) -> str:
    return f"{_CACHE_KEY_PREFIX}{network_tag}"


def _load_from_diskcache(network_tag: str) -> nx.DiGraph | None:
    """Try to load a serialised graph from diskcache. Returns None on miss/error."""
    try:
        from world.cache import get as _cache_get
        raw = _cache_get(_cache_key(network_tag))
        if raw is not None:
            return pickle.loads(raw)
    except Exception:
        pass
    return None


def _save_to_diskcache(network_tag: str, graph: nx.DiGraph):
    """Serialise and store a graph in diskcache."""
    try:
        from world.cache import set as _cache_set
        _cache_set(_cache_key(network_tag), pickle.dumps(graph))
    except Exception:
        pass

# Mirrors SECTOR_TO_ENDPOINT / ENDPOINT_TO_SECTOR from tunnels.py
# (imported lazily to avoid circular imports)
def _get_sector_maps():
    from world.movement.tunnels import SECTOR_TO_ENDPOINT, ENDPOINT_TO_SECTOR
    return SECTOR_TO_ENDPOINT, ENDPOINT_TO_SECTOR


def _get_tunnel_network_tag(room):
    """Return the tunnel_network tag for this room, or None."""
    if not room or not hasattr(room, "tags"):
        return None
    try:
        tags = room.tags.get(category="tunnel_network", return_list=True) or []
    except TypeError:
        tags = []
    return tags[0] if tags else None


def _build_graph(network_tag: str) -> nx.DiGraph:
    """
    Build a directed graph for a tunnel network.
    Nodes: room.id (int)
    Edges: (src_room.id, dest_room.id) for each exit in the network.
    Node attributes: endpoint_tag (str or None), room_obj reference (weak).
    """
    G = nx.DiGraph()
    try:
        all_rooms = search_tag(network_tag, category="tunnel_network") or []
    except Exception:
        all_rooms = []

    _, ENDPOINT_TO_SECTOR = _get_sector_maps()

    for room in all_rooms:
        # Collect endpoint tags for this room
        try:
            ep_tags = room.tags.get(category="tunnel_endpoint", return_list=True) or []
        except TypeError:
            ep_tags = []
        ep_tag = next((t for t in ep_tags if t in ENDPOINT_TO_SECTOR), None)

        G.add_node(room.id, endpoint_tag=ep_tag, room_id=room.id)

        # Add directed edges for each exit
        for obj in room.contents:
            if not isinstance(obj, DefaultExit):
                continue
            dest = getattr(obj, "destination", None)
            if not dest:
                continue
            # Only include exits that stay within the same network
            dest_network = _get_tunnel_network_tag(dest)
            if dest_network != network_tag:
                continue
            G.add_edge(room.id, dest.id, exit_key=getattr(obj, "key", ""))

    return G


def get_tunnel_graph(network_tag: str) -> nx.DiGraph:
    """Return the cached DiGraph for network_tag, building it if needed.
    Checks diskcache first so the graph survives server reloads."""
    if network_tag not in _TUNNEL_GRAPHS:
        cached = _load_from_diskcache(network_tag)
        if cached is not None:
            _TUNNEL_GRAPHS[network_tag] = cached
        else:
            graph = _build_graph(network_tag)
            _TUNNEL_GRAPHS[network_tag] = graph
            _save_to_diskcache(network_tag, graph)
    return _TUNNEL_GRAPHS[network_tag]


def invalidate_tunnel_graph(network_tag: str):
    """
    Discard the cached graph for network_tag so it is rebuilt on next use.
    Call this whenever tunnel topology changes (room tagged/untagged, exit added/removed).
    """
    _TUNNEL_GRAPHS.pop(network_tag, None)
    try:
        from world.cache import delete as _cache_delete
        _cache_delete(_cache_key(network_tag))
    except Exception:
        pass


def invalidate_all_tunnel_graphs():
    """Discard all cached tunnel graphs (e.g. after a server reload)."""
    _TUNNEL_GRAPHS.clear()
    try:
        from world.cache import clear as _cache_clear
        _cache_clear()
    except Exception:
        pass


def _find_endpoint_room_id(network_tag: str, sector: str) -> int | None:
    """Return the room ID of the endpoint for sector in network_tag, or None."""
    SECTOR_TO_ENDPOINT, _ = _get_sector_maps()
    ep_tag = SECTOR_TO_ENDPOINT.get(sector)
    if not ep_tag:
        return None
    G = get_tunnel_graph(network_tag)
    for node_id, data in G.nodes(data=True):
        if data.get("endpoint_tag") == ep_tag:
            return node_id
    return None


def find_tunnel_route(start_room, destination_sector: str) -> list[int] | None:
    """
    Find the shortest route from start_room to the endpoint for destination_sector.

    Drop-in replacement for _find_tunnel_route in world/movement/tunnels.py.

    Args:
        start_room: Evennia room object (must be in a tunnel network).
        destination_sector (str): Sector name (e.g. "slums", "guild").

    Returns:
        list[int]: Room IDs of the path (excluding start_room), or None if no route.
    """
    if not start_room:
        return None
    network_tag = _get_tunnel_network_tag(start_room)
    if not network_tag:
        return None

    dest_id = _find_endpoint_room_id(network_tag, destination_sector)
    if dest_id is None:
        return None

    G = get_tunnel_graph(network_tag)
    if start_room.id not in G:
        # Room not in graph yet — rebuild
        invalidate_tunnel_graph(network_tag)
        G = get_tunnel_graph(network_tag)
    if start_room.id not in G or dest_id not in G:
        return None

    try:
        path = nx.shortest_path(G, source=start_room.id, target=dest_id)
        return path[1:]  # exclude start
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def get_eta_seconds(start_room, destination_sector: str, speed_class: str = "normal") -> int | None:
    """
    Return estimated autopilot travel time in seconds.

    Args:
        start_room: Evennia room object.
        destination_sector (str): Target sector.
        speed_class (str): Vehicle speed class ("slow", "normal", "fast").

    Returns:
        int: Estimated seconds, or None if no route.
    """
    from world.movement.tunnels import AUTOPILOT_STEP_DELAY
    route = find_tunnel_route(start_room, destination_sector)
    if route is None:
        return None
    step_delay = AUTOPILOT_STEP_DELAY.get(speed_class, 4)
    return len(route) * step_delay


def get_valid_destinations(room) -> list[str]:
    """
    Return sector names reachable from this room via the tunnel graph.
    Mirrors tunnels._get_valid_destinations but uses the cached graph.
    """
    network_tag = _get_tunnel_network_tag(room)
    if not network_tag:
        return []

    _, ENDPOINT_TO_SECTOR = _get_sector_maps()
    G = get_tunnel_graph(network_tag)

    if room.id not in G:
        return []

    # Find current endpoint tags (if any) so we exclude where we already are
    try:
        current_ep_tags = room.tags.get(category="tunnel_endpoint", return_list=True) or []
    except TypeError:
        current_ep_tags = []

    destinations = []
    for node_id, data in G.nodes(data=True):
        ep_tag = data.get("endpoint_tag")
        if not ep_tag:
            continue
        if ep_tag in current_ep_tags:
            continue
        sector = ENDPOINT_TO_SECTOR.get(ep_tag)
        if sector and nx.has_path(G, room.id, node_id):
            destinations.append(sector)
    return destinations
