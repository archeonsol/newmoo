"""
Matrix/network utility functions.

Functions for checking network coverage, finding networked devices,
and querying router access points.
"""


def room_has_network_coverage(room, include_matrix_nodes=False):
    """
    Check if a room has active Matrix network coverage.

    Args:
        room: The room object to check
        include_matrix_nodes (bool): If True, MatrixNode rooms are always
            considered to have coverage regardless of router state.
            Defaults to False so callers must opt in explicitly.

    Returns:
        bool: True if the room has an active and online network router, False otherwise

    Examples:
        >>> room_has_network_coverage(my_room)
        True
        >>> room_has_network_coverage(None)
        False
    """
    if not room:
        return False

    if include_matrix_nodes:
        from typeclasses.matrix.rooms import MatrixNode
        if isinstance(room, MatrixNode):
            return True

    router_dbref = getattr(room.db, 'network_router', None)
    if not router_dbref:
        return False

    # Verify the router exists and is online
    from typeclasses.matrix.objects import Router
    try:
        router = Router.objects.get(pk=router_dbref)
        return getattr(router.db, 'online', False)
    except Router.DoesNotExist:
        return False


def get_networked_devices(room):
    """
    Get all networked devices in a room (recursively searching contents).

    Args:
        room: The room object to search

    Returns:
        list: List of NetworkedMixin objects found in the room

    Examples:
        >>> devices = get_networked_devices(my_room)
        >>> len(devices)
        3
    """
    from typeclasses.matrix.mixins import NetworkedMixin

    devices = []

    def find_devices_recursive(container, depth=0):
        """Recursively search container and inventory for networked devices."""
        if depth >= 10:
            return
        for obj in container.contents:
            if isinstance(obj, NetworkedMixin):
                devices.append(obj)
            find_devices_recursive(obj, depth + 1)

    if room:
        find_devices_recursive(room)

    return devices


def get_router_access_points(router):
    """
    Get all rooms (access points) linked to a specific router.

    Args:
        router: The Router object

    Returns:
        list: List of Room objects linked to this router

    Examples:
        >>> aps = get_router_access_points(my_router)
        >>> len(aps)
        5
    """
    from typeclasses.rooms import Room

    if not router:
        return []

    linked_rooms = []
    for room in Room.objects.all():
        room_router_pk = getattr(room.db, 'network_router', None)
        if room_router_pk == router.pk:
            linked_rooms.append(room)

    return linked_rooms
