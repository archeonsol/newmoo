"""
Wilderness coordinate graph via networkx.

Provides a grid_2d_graph covering the wilderness map bounds (-100..100 in
both x and y) for:

  - Coordinate routing: shortest path between two (x, y) coordinates.
  - Biome region queries: find all coordinates in a contiguous biome region.
  - Chokepoint analysis: betweenness centrality to identify high-traffic
    coordinates for placing encounters or landmarks.
  - Blocked-cell support: remove nodes for impassable coordinates (cliffs,
    walls, etc.) so routing avoids them.

The graph is built lazily and cached at module level. Call
invalidate_wilderness_graph() after map topology changes.

Public API:
    get_wilderness_graph() -> nx.Graph
    wilds_route(start_coord, end_coord) -> list[tuple[int,int]] | None
    wilds_route_length(start_coord, end_coord) -> int | None
    get_biome_region(coord, biome_tag) -> set[tuple[int,int]]
    block_coord(coord) / unblock_coord(coord)
    get_chokepoints(top_n) -> list[tuple[tuple,float]]
    invalidate_wilderness_graph()
"""

import networkx as nx

# Wilderness map bounds (inclusive)
WILDS_MIN = -100
WILDS_MAX = 100
WILDS_SIZE = WILDS_MAX - WILDS_MIN + 1  # 201

# Module-level cache
_WILDS_GRAPH: nx.Graph | None = None

# Coordinates tagged as impassable (e.g. cliff faces, solid walls)
_BLOCKED_COORDS: set[tuple[int, int]] = set()

# Per-coordinate biome tags: {(x, y): biome_str}
# Populated by wilderness_map.py when rooms are prepared.
_COORD_BIOMES: dict[tuple[int, int], str] = {}


def _coord_to_node(coord: tuple[int, int]) -> tuple[int, int]:
    """Convert game coordinate (x, y) to graph node (x+100, y+100)."""
    return (coord[0] - WILDS_MIN, coord[1] - WILDS_MIN)


def _node_to_coord(node: tuple[int, int]) -> tuple[int, int]:
    """Convert graph node (nx, ny) back to game coordinate (x, y)."""
    return (node[0] + WILDS_MIN, node[1] + WILDS_MIN)


def _build_coord_graph() -> nx.Graph:
    """
    Build a 201x201 grid graph for the wilderness coordinate space.
    Nodes are (offset_x, offset_y) tuples; blocked coords are removed.
    """
    G = nx.grid_2d_graph(WILDS_SIZE, WILDS_SIZE)
    for coord in _BLOCKED_COORDS:
        node = _coord_to_node(coord)
        if G.has_node(node):
            G.remove_node(node)
    return G


def get_wilderness_graph() -> nx.Graph:
    """Return the cached wilderness coordinate graph, building it if needed."""
    global _WILDS_GRAPH
    if _WILDS_GRAPH is None:
        _WILDS_GRAPH = _build_coord_graph()
    return _WILDS_GRAPH


def invalidate_wilderness_graph():
    """Discard the cached graph so it is rebuilt on next use."""
    global _WILDS_GRAPH
    _WILDS_GRAPH = None


def block_coord(coord: tuple[int, int]):
    """
    Mark a coordinate as impassable (e.g. a cliff face).
    Invalidates the cached graph.
    """
    _BLOCKED_COORDS.add(coord)
    invalidate_wilderness_graph()


def unblock_coord(coord: tuple[int, int]):
    """Remove an impassable marker from a coordinate."""
    _BLOCKED_COORDS.discard(coord)
    invalidate_wilderness_graph()


def set_coord_biome(coord: tuple[int, int], biome: str):
    """
    Record the biome tag for a coordinate.
    Called by ColonyWildernessProvider.at_prepare_room when a room is prepared.
    """
    _COORD_BIOMES[coord] = biome


def get_coord_biome(coord: tuple[int, int]) -> str | None:
    """Return the biome tag for a coordinate, or None if unknown."""
    return _COORD_BIOMES.get(coord)


def wilds_route(
    start_coord: tuple[int, int],
    end_coord: tuple[int, int],
) -> list[tuple[int, int]] | None:
    """
    Find the shortest path between two wilderness coordinates.

    Args:
        start_coord: (x, y) game coordinate.
        end_coord: (x, y) game coordinate.

    Returns:
        list of (x, y) tuples from start to end (inclusive), or None if no path.
    """
    G = get_wilderness_graph()
    s = _coord_to_node(start_coord)
    e = _coord_to_node(end_coord)
    if not G.has_node(s) or not G.has_node(e):
        return None
    try:
        path = nx.shortest_path(G, source=s, target=e)
        return [_node_to_coord(n) for n in path]
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def wilds_route_length(
    start_coord: tuple[int, int],
    end_coord: tuple[int, int],
) -> int | None:
    """
    Return the number of steps between two wilderness coordinates,
    or None if no path exists.
    """
    G = get_wilderness_graph()
    s = _coord_to_node(start_coord)
    e = _coord_to_node(end_coord)
    if not G.has_node(s) or not G.has_node(e):
        return None
    try:
        return nx.shortest_path_length(G, source=s, target=e)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def get_biome_region(
    coord: tuple[int, int],
    biome: str,
) -> set[tuple[int, int]]:
    """
    Return the set of all coordinates contiguous with coord that share the
    same biome tag. Uses BFS over the graph limited to matching biome nodes.

    Useful for:
    - Area-wide weather/event propagation within a biome.
    - Scavenge density calculation per biome region.
    - Encounter placement within a biome zone.

    Args:
        coord: Starting (x, y) coordinate.
        biome: Biome tag string (e.g. "grasslands", "hills").

    Returns:
        set of (x, y) tuples in the contiguous biome region.
    """
    G = get_wilderness_graph()
    start_node = _coord_to_node(coord)
    if not G.has_node(start_node):
        return set()

    # Build a subgraph of only nodes with the matching biome
    biome_nodes = {
        _coord_to_node(c)
        for c, b in _COORD_BIOMES.items()
        if b == biome and G.has_node(_coord_to_node(c))
    }
    if start_node not in biome_nodes:
        return set()

    subgraph = G.subgraph(biome_nodes)
    try:
        component = nx.node_connected_component(subgraph, start_node)
        return {_node_to_coord(n) for n in component}
    except nx.NodeNotFound:
        return set()


def get_chokepoints(top_n: int = 10) -> list[tuple[tuple[int, int], float]]:
    """
    Return the top_n coordinates with the highest betweenness centrality —
    these are the most-traversed points on the map and are good candidates
    for encounter placement, landmarks, or patrol routes.

    Note: betweenness_centrality on a 201x201 graph is expensive (~2s).
    Use approximate=True (k parameter) for large maps or call offline.

    Args:
        top_n: Number of top chokepoints to return.

    Returns:
        list of ((x, y), centrality_score) sorted descending by score.
    """
    G = get_wilderness_graph()
    # Use approximate centrality with k=200 samples for performance
    centrality = nx.betweenness_centrality(G, k=min(200, len(G)), normalized=True)
    sorted_nodes = sorted(centrality.items(), key=lambda kv: kv[1], reverse=True)
    return [(_node_to_coord(node), score) for node, score in sorted_nodes[:top_n]]


def coords_within_radius(
    center: tuple[int, int],
    radius: int,
) -> list[tuple[int, int]]:
    """
    Return all valid wilderness coordinates within graph-distance `radius`
    of center. Uses BFS (single-source shortest path length).

    Args:
        center: (x, y) coordinate.
        radius: Maximum number of steps.

    Returns:
        list of (x, y) coordinates within radius (including center).
    """
    G = get_wilderness_graph()
    node = _coord_to_node(center)
    if not G.has_node(node):
        return []
    lengths = nx.single_source_shortest_path_length(G, node, cutoff=radius)
    return [_node_to_coord(n) for n in lengths]
