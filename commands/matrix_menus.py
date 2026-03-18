"""
Matrix Menu System

EvMenu nodes for Matrix navigation and interaction.

Router Access Menu:
- Lists access points (rooms) connected to a router
- Shows devices in each access point
- Allows routing to device interfaces (creates ephemeral checkpoint/interface rooms)
"""

from evennia.utils.evmenu import EvMenu
from evennia.utils import logger
from typeclasses.matrix.mixins import NetworkedMixin


def router_main_menu(caller, raw_string, **kwargs):
    """
    Main router interface menu.

    Provides options for routing, proxy management, and browsing access points.
    """
    router = kwargs.get("router")
    if not router:
        # Try to get from menu storage
        router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None
    if not router:
        caller.msg("Error: No router found.")
        return None

    # Store router in menu for other nodes
    if hasattr(caller.ndb, '_evmenu'):
        caller.ndb._evmenu.router = router

    # Find all rooms linked to this router
    from evennia.objects.models import ObjectDB
    from typeclasses.rooms import Room

    linked_rooms = []
    for room in Room.objects.all():
        room_router_dbref = getattr(room.db, 'network_router', None)
        if room_router_dbref == router.pk:
            linked_rooms.append(room)

    text = f"|c=== {router.key} Interface ===|n\n\n"
    text += f"Status: {router.get_status()}\n\n"

    # Check if caller has a proxy tunnel
    from typeclasses.matrix.avatars import MatrixAvatar
    has_proxy = False
    if isinstance(caller, MatrixAvatar):
        has_proxy = bool(caller.db.proxy_router)

    text += "|wa|n. Route to access point\n"
    text += "|wb|n. Browse APs |x(testing only)|n\n"

    if has_proxy:
        text += "|we|n. Route to proxy exit\n"
    else:
        text += "|we|n. Route to session origin\n"

    text += "|ws|n. View proxy status\n"

    if has_proxy:
        text += "|wp|n. Close proxy tunnel\n"
    else:
        text += "|wp|n. Open proxy tunnel\n"

    text += "|wq|n. Exit router interface"

    options = []

    options.append({
        "key": ("a", "route", "access"),
        "desc": "Route to access point",
        "goto": "route_to_access_point"
    })

    options.append({
        "key": ("b", "browse"),
        "desc": "Browse APs (testing only)",
        "goto": "browse_access_points"
    })

    if has_proxy:
        options.append({
            "key": ("e", "entry", "back", "previous"),
            "desc": "Route to proxy exit",
            "goto": "route_to_entry_point"
        })
    else:
        options.append({
            "key": ("e", "entry", "back", "previous"),
            "desc": "Route to session origin",
            "goto": "route_to_entry_point"
        })

    options.append({
        "key": ("s", "status"),
        "desc": "View proxy status",
        "goto": "view_proxy_status"
    })

    if has_proxy:
        options.append({
            "key": ("p", "proxy"),
            "desc": "Close proxy tunnel",
            "goto": "close_proxy_tunnel"
        })
    else:
        options.append({
            "key": ("p", "proxy"),
            "desc": "Open proxy tunnel",
            "goto": "open_proxy_tunnel"
        })

    options.append({
        "key": ("q", "quit", "exit"),
        "desc": "Exit",
        "goto": "router_exit"
    })

    return text, options


def route_to_access_point(caller, raw_string, **kwargs):
    """
    Prompt for AP Matrix ID and route to it.

    User must enter the AP ID (with or without ^ prefix).
    """
    router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None

    if not router:
        text = "|rError: No router found.|n\n\n"
        text += "|xPress any key to return to router menu|n"
        return text, [{"key": "_default", "goto": ("router_main_menu", {"router": router})}]

    text = f"|c=== Route to Access Point ===|n\n\n"
    text += "Enter the Matrix ID of the access point you wish to route to.\n"
    text += "Format: ^XXXXXX or XXXXXX\n\n"
    text += "|xType 'back' or 'b' to return to router menu|n"

    options = []
    options.append({
        "key": "_default",
        "goto": ("resolve_access_point", {"router": router})
    })
    options.append({
        "key": ("back", "b"),
        "goto": ("router_main_menu", {"router": router})
    })

    return text, options


def resolve_access_point(caller, raw_string, **kwargs):
    """
    Look up the AP ID and route to devices at that location.
    """
    router = kwargs.get("router")
    if not router:
        router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None

    if not router:
        caller.msg("|rError: No router found.|n")
        return ("router_access_points", {"router": router})

    ap_input = raw_string.strip()

    # Allow back or empty input
    if not ap_input or ap_input.lower() in ('back', 'b', 'return'):
        return ("router_main_menu", {"router": router})

    # Strip ^ prefix if present, accept either format
    if ap_input.startswith("^"):
        ap_input = ap_input[1:]

    # Normalize to uppercase
    ap_id = "^" + ap_input.upper()

    # Look up the AP by Matrix ID
    from world.matrix_ids import lookup_matrix_id
    room = lookup_matrix_id(ap_id)

    if not room:
        caller.msg(f"|rAccess point {ap_id} not found.|n")
        return ("route_to_access_point", {"router": router})

    # Verify this AP is connected to this router
    from typeclasses.rooms import Room
    if not isinstance(room, Room):
        caller.msg(f"|rInvalid access point.|n")
        return ("route_to_access_point", {"router": router})

    room_router_pk = getattr(room.db, 'network_router', None)
    if room_router_pk != router.pk:
        caller.msg(f"|rAccess point {ap_id} is not connected to this router.|n")
        return ("route_to_access_point", {"router": router})

    # Valid AP, show devices
    return ("access_point_devices", {"room": room})


def browse_access_points(caller, raw_string, **kwargs):
    """
    Browse all access points connected to this router (testing only).
    """
    router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None

    if not router:
        text = "|rError: No router found.|n\n\n"
        text += "|xPress any key to return to router menu|n"
        return text, [{"key": "_default", "goto": ("router_main_menu", {"router": router})}]

    # Find all rooms linked to this router
    from typeclasses.rooms import Room

    linked_rooms = []
    for room in Room.objects.all():
        room_router_dbref = getattr(room.db, 'network_router', None)
        if room_router_dbref == router.pk:
            linked_rooms.append(room)

    if not linked_rooms:
        text = f"|c=== {router.key} - Browse APs (testing) ===|n\n\n"
        text += "No access points connected to this router.\n"
        text += "(Use 'mlink' in meatspace rooms to connect them to this router)\n\n"
        text += "|xb|n. Back to router menu"

        options = [{
            "key": ("b", "back"),
            "desc": "Back",
            "goto": ("router_main_menu", {"router": router})
        }]

        return text, options

    # Sort rooms by key for consistent display
    linked_rooms.sort(key=lambda r: r.key)

    text = f"|c=== {router.key} - Browse APs (testing) ===|n\n\n"
    text += f"Connected Access Points: {len(linked_rooms)}\n\n"

    options = []

    for i, room in enumerate(linked_rooms, 1):
        ap_name = room.key
        matrix_id = room.get_matrix_id() if hasattr(room, 'get_matrix_id') else "^UNKNOWN"
        text += f"  |w{i}|n. {ap_name} |m({matrix_id})|n\n"

        options.append({
            "desc": f"Access {ap_name}",
            "goto": ("access_point_devices", {"room": room})
        })

    text += "\n|xb|n. Back to router menu"

    options.append({
        "key": ("b", "back"),
        "desc": "Back",
        "goto": ("router_main_menu", {"router": router})
    })

    return text, options


def access_point_devices(caller, raw_string, **kwargs):
    """
    Show all networked devices in a specific access point.

    Displays devices with their type and allows routing to their interface.
    """
    # Get router from menu storage
    router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None
    room = kwargs.get("room")

    if not router or not room:
        text = "|rError: Missing router or room data.|n\n\n"
        text += "|xPress any key to return to router menu|n"
        return text, [{"key": "_default", "goto": ("router_main_menu", {"router": router})}]

    # Find all networked devices in this room (recursively check inventory)
    devices = []

    def find_devices_recursive(container):
        """Recursively search container and inventory for networked devices."""
        for obj in container.contents:
            if isinstance(obj, NetworkedMixin):
                devices.append(obj)
            # Also search this object's contents (inventory, containers, etc.)
            if hasattr(obj, 'contents'):
                find_devices_recursive(obj)

    find_devices_recursive(room)

    if not devices:
        text = f"|c=== {room.key} ===|n\n\n"
        text += "No networked devices found in this access point.\n\n"
        text += "|xb|n. Back to access points\n"

        return text, [{
            "key": ("b", "back"),
            "desc": "Back",
            "goto": ("router_main_menu", {"router": router})
        }]

    # Sort devices by key
    devices.sort(key=lambda d: d.key)

    text = f"|c=== {room.key} - Devices ===|n\n\n"
    text += f"Access Point: |w{room.key}|n\n"
    text += f"Devices: {len(devices)}\n\n"

    options = []

    for i, device in enumerate(devices, 1):
        device_type = getattr(device.db, 'device_type', 'unknown')
        matrix_id = device.get_matrix_id() if hasattr(device, 'get_matrix_id') else "^UNKNOWN"

        # Check security level if set
        security = getattr(device.db, 'security_level', 0)
        security_str = f" |r[SEC:{security}]|n" if security > 0 else ""

        display_name = f"{device_type} {matrix_id}"
        text += f"  |w{i}|n. {display_name}{security_str}\n"

        options.append({
            "desc": f"Route to {display_name}",
            "goto": ("route_to_device", {"device": device})
        })

    text += "\n|xb|n. Back to access points"

    options.append({
        "key": ("b", "back"),
        "desc": "Back",
        "goto": ("router_main_menu", {"router": router})
    })

    return text, options


def route_to_device(caller, raw_string, **kwargs):
    """
    Route to a specific device's interface.

    Creates the device's ephemeral checkpoint and interface rooms,
    then teleports the caller to the checkpoint.
    """
    # Get router from menu storage
    router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None
    device = kwargs.get("device")

    if not device:
        text = "|rError: Device not found.|n\n\n"
        text += "|xPress any key to return to router menu|n"
        return text, [{"key": "_default", "goto": ("router_main_menu", {"router": router})}]

    from evennia.utils import delay

    # Get or create the device's ephemeral cluster
    try:
        cluster = device.get_or_create_cluster()
    except Exception as e:
        logger.log_trace(f"matrix_menus._route_to_device get_or_create_cluster: {e}")
        caller.msg(f"|rConnection failed: Unable to establish interface.|n")
        caller.msg(f"Error: {e}")
        return None

    if not cluster:
        caller.msg(f"|rConnection failed: Device interface unavailable.|n")
        return None

    checkpoint = cluster.get('checkpoint')
    interface = cluster.get('interface')

    if not checkpoint or not interface:
        caller.msg(f"|rConnection failed: Incomplete interface cluster.|n")
        return None

    # Get router and access point info for link path
    router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None
    router_name = router.key if router else "unknown"
    access_point_name = device.location.key if device.location else "unknown"
    link_path = f"link://{router_name}/{access_point_name}/{device.key}"

    # Progressive connection messages with delays
    caller.msg(f"|cResolving spanning tree...|n")

    def _link_established():
        caller.msg(f"|gLink established.|n")
        delay(0.8, _route_to_device)

    def _route_to_device():
        caller.msg(f"|cRouting to |w{link_path}|c...|n")
        delay(0.8, _do_move)

    def _do_move():
        # Announce departure to current room
        if caller.location:
            caller.location.msg_contents(
                f"{caller.key} disappears in a flicker of data.",
                exclude=[caller]
            )

        # Move to checkpoint (let Evennia handle auto-look)
        caller.move_to(checkpoint)

        # Announce arrival
        checkpoint.msg_contents(
            f"{caller.key} materializes from the data stream.",
            exclude=[caller]
        )

    delay(0.8, _link_established)

    # Exit the menu
    return None


def route_to_entry_point(caller, raw_string, **kwargs):
    """
    Route back to the entry point router.

    Traces from avatar -> rig -> meatspace room -> entry router,
    then routes the avatar to that router.
    """
    from typeclasses.matrix.avatars import MatrixAvatar

    if not isinstance(caller, MatrixAvatar):
        router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None
        text = "|rError: Only Matrix avatars can route to entry points.|n\n\n"
        text += "|xPress any key to return to router menu|n"
        return text, [{"key": "_default", "goto": ("router_main_menu", {"router": router})}]

    # Get the rig this avatar is connected through
    rig = caller.db.entry_device
    if not rig:
        router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None
        text = "|rError: No entry device found. Cannot determine entry point.|n\n\n"
        text += "|xPress any key to return to router menu|n"
        return text, [{"key": "_default", "goto": ("router_main_menu", {"router": router})}]

    # Get the meatspace room the rig is in
    rig_room = rig.location
    if not rig_room:
        router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None
        text = "|rError: Entry device has no location.|n\n\n"
        text += "|xPress any key to return to router menu|n"
        return text, [{"key": "_default", "goto": ("router_main_menu", {"router": router})}]

    # Get the router that room is linked to
    entry_router_pk = getattr(rig_room.db, 'network_router', None)
    if not entry_router_pk:
        router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None
        text = "|rError: Entry location has no network router.|n\n\n"
        text += "|xPress any key to return to router menu|n"
        return text, [{"key": "_default", "goto": ("router_main_menu", {"router": router})}]

    # Load the entry router
    from typeclasses.matrix.objects import Router
    try:
        entry_router = Router.objects.get(pk=entry_router_pk)
    except Router.DoesNotExist:
        router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None
        text = "|rError: Entry router not found.|n\n\n"
        text += "|xPress any key to return to router menu|n"
        return text, [{"key": "_default", "goto": ("router_main_menu", {"router": router})}]

    # Check if we're already at the entry router's location
    if caller.location == entry_router.location:
        router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None
        text = "|yYou are already at your entry point router.|n\n\n"
        text += "|xPress any key to return to router menu|n"
        return text, [{"key": "_default", "goto": ("router_main_menu", {"router": router})}]

    # Route to the entry router with delays
    from evennia.utils import delay

    caller.msg(f"|cResolving route to entry point...|n")

    def _routing():
        caller.msg(f"|cRouting to |w{entry_router.key}|c...|n")
        delay(0.8, _do_move)

    def _do_move():
        # Announce departure
        if caller.location:
            caller.location.msg_contents(
                f"{caller.key} disappears in a flicker of data.",
                exclude=[caller]
            )

        # Move to entry router's location (the room it's in)
        destination = entry_router.location
        if not destination:
            caller.msg("|rError: Entry router has no location.|n")
            return

        caller.move_to(destination)

        # Announce arrival
        destination.msg_contents(
            f"{caller.key} materializes from the data stream.",
            exclude=[caller]
        )

    delay(0.8, _routing)

    # Exit the menu
    return None


def router_exit(caller, raw_string, **kwargs):
    """Exit the router access menu."""
    caller.msg("|cDisconnecting from router interface...|n")
    return None


# Helper function to get all rooms linked to a router
def get_linked_rooms(router):
    """
    Get all rooms linked to a specific router.

    Args:
        router: The Router object

    Returns:
        list: List of Room objects linked to this router
    """
    from evennia.objects.models import ObjectDB
    from typeclasses.rooms import Room

    linked_rooms = []
    for room in Room.objects.all():
        room_router_dbref = getattr(room.db, 'network_router', None)
        if room_router_dbref == router.pk:
            linked_rooms.append(room)

    return linked_rooms


def open_proxy_tunnel(caller, raw_string, **kwargs):
    """
    Open a proxy tunnel at the current router.

    Cannot open if already have one open.
    """
    from typeclasses.matrix.avatars import MatrixAvatar

    router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None

    if not router:
        text = "|rError: No router found.|n\n\n"
        text += "|xPress any key to return to router menu|n"
        return text, [{"key": "_default", "goto": ("router_main_menu", {"router": router})}]

    if not isinstance(caller, MatrixAvatar):
        text = "|rError: Only Matrix avatars can open proxy tunnels.|n\n\n"
        text += "|xPress any key to return to router menu|n"
        return text, [{"key": "_default", "goto": ("router_main_menu", {"router": router})}]

    # Check if already has proxy
    if caller.db.proxy_router:
        text = "|rYou already have a proxy tunnel open.|n\n"
        text += "You must close your existing proxy before opening a new one.\n\n"
        text += "|xPress any key to return to router menu|n"
        return text, [{"key": "_default", "goto": ("router_main_menu", {"router": router})}]

    # Open the proxy tunnel
    caller.db.proxy_router = router.pk

    text = f"|gProxy tunnel opened at {router.key}.|n\n"
    text += "Your session origin now routes through this proxy.\n\n"
    text += "|xPress any key to return to router menu|n"
    return text, [{"key": "_default", "goto": ("router_main_menu", {"router": router})}]


def close_proxy_tunnel(caller, raw_string, **kwargs):
    """
    Close the proxy tunnel.

    Can only close from session origin router or the proxy router itself.
    """
    from typeclasses.matrix.avatars import MatrixAvatar

    router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None

    if not router:
        text = "|rError: No router found.|n\n\n"
        text += "|xPress any key to return to router menu|n"
        return text, [{"key": "_default", "goto": ("router_main_menu", {"router": router})}]

    if not isinstance(caller, MatrixAvatar):
        text = "|rError: Only Matrix avatars can close proxy tunnels.|n\n\n"
        text += "|xPress any key to return to router menu|n"
        return text, [{"key": "_default", "goto": ("router_main_menu", {"router": router})}]

    # Check if has proxy
    if not caller.db.proxy_router:
        text = "|rYou don't have a proxy tunnel open.|n\n\n"
        text += "|xPress any key to return to router menu|n"
        return text, [{"key": "_default", "goto": ("router_main_menu", {"router": router})}]

    # Get session origin router (from rig's room)
    rig = caller.db.entry_device
    if not rig or not hasattr(rig, 'location'):
        text = "|rError: Cannot determine session origin.|n\n\n"
        text += "|xPress any key to return to router menu|n"
        return text, [{"key": "_default", "goto": ("router_main_menu", {"router": router})}]

    rig_room = rig.location
    if not rig_room:
        text = "|rError: Cannot determine session origin.|n\n\n"
        text += "|xPress any key to return to router menu|n"
        return text, [{"key": "_default", "goto": ("router_main_menu", {"router": router})}]

    session_origin_router_pk = getattr(rig_room.db, 'network_router', None)
    proxy_router_pk = caller.db.proxy_router

    # Check if at session origin or proxy router
    if router.pk != session_origin_router_pk and router.pk != proxy_router_pk:
        text = "|rYou can only close your proxy tunnel from your session origin router or the proxy router itself.|n\n\n"
        text += "|xPress any key to return to router menu|n"
        return text, [{"key": "_default", "goto": ("router_main_menu", {"router": router})}]

    # Close the proxy tunnel
    caller.db.proxy_router = None

    text = f"|gProxy tunnel closed.|n\n"
    text += "Your session origin now routes directly to your entry point.\n\n"
    text += "|xPress any key to return to router menu|n"
    return text, [{"key": "_default", "goto": ("router_main_menu", {"router": router})}]


def view_proxy_status(caller, raw_string, **kwargs):
    """
    Display current proxy tunnel status.
    """
    from typeclasses.matrix.avatars import MatrixAvatar

    router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None

    text = f"|c=== Proxy Tunnel Status ===|n\n\n"

    if not isinstance(caller, MatrixAvatar):
        text += "|rError: Only Matrix avatars can have proxy tunnels.|n\n"
    elif not caller.db.proxy_router:
        text += "Status: |xNo proxy tunnel active|n\n\n"
        text += "You can open a proxy tunnel at any router to mask your session origin.\n"
    else:
        # Get proxy router info
        try:
            from typeclasses.matrix.objects import Router
            proxy_router = Router.objects.get(pk=caller.db.proxy_router)
            online_status = "|g[ONLINE]|n" if getattr(proxy_router.db, 'online', False) else "|r[OFFLINE]|n"
            text += f"Status: |gProxy tunnel active|n\n\n"
            text += f"Proxy Router: {proxy_router.key} {online_status}\n"
            text += f"Proxy Location: {proxy_router.location.key if proxy_router.location else 'Unknown'}\n\n"
            text += "Your session origin now routes through this proxy.\n"
        except:
            text += "Status: |yProxy tunnel active (router not found)|n\n\n"
            text += "Warning: Proxy router no longer exists.\n"

    # Get session origin info
    if isinstance(caller, MatrixAvatar):
        rig = caller.db.entry_device
        if rig and hasattr(rig, 'location') and rig.location:
            rig_room = rig.location
            session_router_pk = getattr(rig_room.db, 'network_router', None)
            if session_router_pk:
                try:
                    from typeclasses.matrix.objects import Router
                    session_router = Router.objects.get(pk=session_router_pk)
                    text += f"\nSession Origin Router: {session_router.key}\n"
                except:
                    pass

    text += "\n|xPress any key to return to router menu|n"

    options = [{
        "key": "_default",
        "goto": ("router_main_menu", {"router": router})
    }]

    return text, options


# Helper function to get all networked devices in a room
def get_networked_devices(room):
    """
    Get all networked devices in a room.

    Args:
        room: The Room object

    Returns:
        list: List of NetworkedMixin objects in the room
    """
    devices = []
    for obj in room.contents:
        if isinstance(obj, NetworkedMixin):
            devices.append(obj)

    return devices
