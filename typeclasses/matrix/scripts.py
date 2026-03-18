"""
Matrix Scripts

Global scripts for Matrix system maintenance and automation.

MatrixCleanupScript - Periodically removes empty ephemeral Matrix nodes
"""

from evennia.scripts.scripts import DefaultScript


class MatrixCleanupScript(DefaultScript):
    """
    Global script that periodically cleans up empty ephemeral Matrix nodes.

    Runs every CLEANUP_INTERVAL seconds and deletes any MatrixNode where:
    - db.ephemeral is True
    - No avatars are present in the node

    This prevents ephemeral nodes (cameras, locks, simple devices) from
    accumulating in the database after users disconnect.
    """

    def at_script_creation(self):
        """Called when script is first created."""
        self.key = "matrix_cleanup"
        self.desc = "Cleans up empty ephemeral Matrix nodes"
        self.interval = 10  # Run every 10 seconds
        self.repeats = 0  # Run forever
        self.persistent = True  # Survive server restarts
        self.start_delay = True  # Wait one interval before first run

    def at_repeat(self):
        """Called every interval. Scans for and deletes empty ephemeral nodes and ejects avatars from disconnected devices."""
        from typeclasses.matrix.rooms import MatrixNode
        from typeclasses.matrix.avatars import MatrixAvatar
        from typeclasses.rooms import Room
        from evennia.utils import logger
        import time

        start_time = time.time()

        # Get all MatrixNodes and filter for ephemeral ones in Python
        # (Can't filter on Attributes via SQL)
        all_nodes = MatrixNode.objects.all()
        ephemeral_nodes = [node for node in all_nodes if getattr(node.db, 'ephemeral', False)]

        logger.log_info(f"Matrix cleanup START: {len(ephemeral_nodes)} ephemeral nodes to check")

        deleted_count = 0
        ejected_count = 0

        # Track which nodes we've already processed (to handle vestibule/interface pairs together)
        processed_nodes = set()

        for node in ephemeral_nodes:
            if node.pk in processed_nodes:
                continue

            parent_device = getattr(node.db, 'parent_object', None)
            if not parent_device:
                continue

            # Get BOTH vestibule and interface for this device
            vestibule_pk = getattr(parent_device.db, 'vestibule_node', None)
            interface_pk = getattr(parent_device.db, 'interface_node', None)

            cluster_nodes = []
            if vestibule_pk:
                try:
                    vestibule = MatrixNode.objects.get(pk=vestibule_pk)
                    cluster_nodes.append(vestibule)
                    processed_nodes.add(vestibule.pk)
                except MatrixNode.DoesNotExist:
                    pass

            if interface_pk:
                try:
                    interface = MatrixNode.objects.get(pk=interface_pk)
                    cluster_nodes.append(interface)
                    processed_nodes.add(interface.pk)
                except MatrixNode.DoesNotExist:
                    pass

            if not cluster_nodes:
                continue

            # Find all avatars in ANY node in the cluster
            avatars = []
            for cluster_node in cluster_nodes:
                avatars.extend([obj for obj in cluster_node.contents if isinstance(obj, MatrixAvatar)])

            # Check if parent device has lost connectivity
            if avatars:
                    logger.log_info(f"  Checking connectivity for {parent_device.key} with {len(avatars)} avatar(s)")
                    # Walk up the location chain to find a Room
                    current_location = parent_device.location
                    room_location = None

                    # Walk up to 10 levels to find a Room (prevents infinite loops)
                    for _ in range(10):
                        if not current_location:
                            break
                        if isinstance(current_location, Room):
                            room_location = current_location
                            break
                        # Go up one level
                        current_location = getattr(current_location, 'location', None)

                    # Check connectivity
                    has_connectivity = False
                    if room_location:
                        router_dbref = getattr(room_location.db, 'network_router', None)
                        if router_dbref:
                            from typeclasses.matrix.objects import Router
                            try:
                                router = Router.objects.get(pk=router_dbref)
                                if getattr(router.db, 'online', False):
                                    has_connectivity = True
                            except Router.DoesNotExist:
                                pass

                    # Eject avatars if no connectivity
                    logger.log_info(f"    Has connectivity: {has_connectivity}")
                    if not has_connectivity:
                        logger.log_info(f"    Ejecting {len(avatars)} avatar(s)")
                        for avatar in avatars:
                            node.msg_contents(
                                f"{avatar.key} is forcibly ejected as the connection fails!",
                                exclude=[avatar]
                            )
                            avatar.msg("|rConnection lost! Device has no network connectivity.|n")

                            # Try to find entry router to move avatar to
                            entry_location = None
                            rig = getattr(avatar.db, 'entry_device', None)
                            if rig:
                                # Walk up rig's location chain to find a Room
                                current_loc = rig.location
                                rig_room = None

                                for _ in range(10):
                                    if not current_loc:
                                        break
                                    if isinstance(current_loc, Room):
                                        rig_room = current_loc
                                        break
                                    current_loc = getattr(current_loc, 'location', None)

                                if rig_room:
                                    entry_router_pk = getattr(rig_room.db, 'network_router', None)
                                    if entry_router_pk:
                                        from typeclasses.matrix.objects import Router
                                        try:
                                            entry_router = Router.objects.get(pk=entry_router_pk)
                                            entry_location = entry_router.location
                                        except Router.DoesNotExist:
                                            pass

                            # Move avatar before disconnecting
                            if entry_location:
                                avatar.msg("|yRouting to entry point before disconnect...|n")
                                avatar.move_to(entry_location)
                                entry_location.msg_contents(
                                    f"{avatar.key} materializes abruptly, connection failing.",
                                    exclude=[avatar]
                                )
                            else:
                                # No entry router, move to Limbo
                                from evennia.objects.models import ObjectDB
                                limbo = ObjectDB.objects.get_id(2)
                                if limbo:
                                    avatar.msg("|yEmergency disconnect to safe location...|n")
                                    avatar.move_to(limbo)

                            # Now force emergency jackout if rig supports it
                            if rig and hasattr(rig, 'disconnect'):
                                avatar.msg("|rEmergency jackout initiated...|n")
                                from typeclasses.matrix.avatars import JACKOUT_EMERGENCY
                                character = avatar.get_controlling_character()
                                if character:
                                    rig.disconnect(character, severity=JACKOUT_EMERGENCY, reason="Device connection lost")

                            ejected_count += 1

            # After ejecting avatars, delete all empty nodes in the cluster
            for cluster_node in cluster_nodes:
                if not any(isinstance(obj, MatrixAvatar) for obj in cluster_node.contents):
                    # Clean up reference in parent device
                    if getattr(parent_device.db, 'vestibule_node', None) == cluster_node.pk:
                        parent_device.db.vestibule_node = None
                    if getattr(parent_device.db, 'interface_node', None) == cluster_node.pk:
                        parent_device.db.interface_node = None

                    cluster_node.delete()
                    deleted_count += 1

        # Log cleanup activity
        elapsed = time.time() - start_time
        logger.log_info(f"Matrix cleanup DONE: ejected {ejected_count} avatar(s), deleted {deleted_count} empty ephemeral node(s) in {elapsed:.3f}s")

    def at_start(self):
        """Called when script starts (including after server restart)."""
        from evennia.utils import logger
        logger.log_info("Matrix cleanup script started")

    def at_stop(self):
        """Called when script stops."""
        from evennia.utils import logger
        logger.log_info("Matrix cleanup script stopped")


class MatrixConnectionScript(DefaultScript):
    """
    Global script that periodically checks Matrix connections.

    Runs every few seconds and validates active connections on dive rigs and
    teleop rigs. Disconnects any connections that have become invalid.
    """

    def at_script_creation(self):
        """Called when script is first created."""
        self.key = "matrix_connection_check"
        self.desc = "Checks Matrix dive and teleop connections periodically"
        self.interval = 10  # Run every 10 seconds
        self.repeats = 0  # Run forever
        self.persistent = True  # Survive server restarts
        self.start_delay = True  # Wait one interval before first run

    def at_repeat(self):
        """Called every interval. Checks all active dive and teleop connections."""
        from evennia.objects.models import ObjectDB

        # Check dive rig connections
        # Can't filter by attribute, so get all DiveRigs and check for active_connection
        from typeclasses.matrix.devices.dive_rig import DiveRig
        all_dive_rigs = DiveRig.objects.all()
        dive_disconnected = 0
        for rig in all_dive_rigs:
            # Only check rigs with active connections
            if getattr(rig.db, 'active_connection', None):
                if hasattr(rig, 'validate_connection') and not rig.validate_connection():
                    dive_disconnected += 1

        # Check teleop connections - iterate all objects and check for controlled_by attribute
        # (Can't filter by attribute directly)
        from typeclasses.matrix.devices.teleop_rig import TeleopRig
        all_teleop_rigs = TeleopRig.objects.all()
        teleop_disconnected = 0
        for rig in all_teleop_rigs:
            # Check if this rig has an active control session
            if not getattr(rig.db, 'controlled_target', None):
                continue

            # Validate the connection
            if hasattr(rig, 'validate_connection') and not rig.validate_connection():
                teleop_disconnected += 1

        # Optional: log disconnection activity
        if dive_disconnected > 0 or teleop_disconnected > 0:
            from evennia.utils import logger
            logger.log_info(f"Connection check: disconnected {dive_disconnected} dive session(s), {teleop_disconnected} teleop session(s)")

    def at_start(self):
        """Called when script starts (including after server restart)."""
        from evennia.utils import logger
        logger.log_info("Matrix connection check script started")

    def at_stop(self):
        """Called when script stops."""
        from evennia.utils import logger
        logger.log_info("Matrix connection check script stopped")
