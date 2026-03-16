"""
Matrix Rooms

Virtual locations within the Matrix. These rooms exist in virtual space and can only
be accessed by diving (via avatar objects). They form the navigable geography
of the city's cyberspace.

All Matrix locations are persistent - device nodes exist as long as the device exists,
hub nodes exist as long as the physical space exists, and spine nodes are permanent
infrastructure.

MatrixRoom - Base class for all virtual Matrix locations
MatrixNode - All Matrix locations (spines, hubs, devices, etc.)
MatrixExit - Connections between Matrix locations
"""

from typeclasses.rooms import Room
from typeclasses.exits import Exit


class MatrixRoom(Room):
    """
    Base class for virtual Matrix locations.

    These rooms exist in the Matrix's virtual space and can only be accessed
    by avatars (characters who are diving). The physical character remains
    in meatspace while their avatar navigates these virtual locations.

    Attributes:
        security_level (int): Security clearance required (0-10, 0=public, 10=maximum)
        parent_object (obj): The physical object/device this node represents (if any)
    """

    default_description = "A featureless virtual space, devoid of detail."

    # Matrix rooms have a different color scheme to distinguish from meatspace
    matrix_name_color = "|c"  # cyan for matrix locations

    def at_object_creation(self):
        """Called when the room is first created."""
        super().at_object_creation()
        self.db.security_level = 0
        self.db.parent_object = None

    def get_display_header(self, looker, **kwargs):
        """Matrix room names use different coloring to distinguish from meatspace."""
        name = self.get_display_name(looker, **kwargs)
        extra = self.get_extra_display_name_info(looker, **kwargs) or ""
        return f"{self.matrix_name_color}{name}{extra}|n"

    def at_object_receive(self, moved_obj, source_location, **kwargs):
        """
        Called when an object enters this room.

        Future implementation will add:
        - Security clearance checks
        - ICE alerts
        - Access logging
        """
        super().at_object_receive(moved_obj, source_location, **kwargs)

        # TODO: Security checks for future implementation
        # if self.db.security_level > 0:
        #     # Check if moved_obj has clearance
        #     # Alert ICE if unauthorized
        #     pass


class MatrixNode(MatrixRoom):
    """
    Virtual location in the Matrix.

    These represent all types of Matrix locations:
    - Spine nodes (relay rooms along the network backbone)
    - Hub nodes (private network spaces for homes/offices)
    - Device nodes (interface spaces for cameras, terminals, etc.)
    - Public spaces (the Cortex, shops, clubs)

    All nodes are persistent. Device nodes exist as long as their parent device
    exists. Hub nodes exist as long as their physical space exists. Spine nodes
    are permanent infrastructure.

    Attributes:
        node_type (str): Type of node (spine, hub, device, public, etc.)
        relay_key (str): Key of the relay this node is associated with (if any)
    """

    default_description = "A vast data space, humming with virtual activity."

    def at_object_creation(self):
        """Called when the node is first created."""
        super().at_object_creation()
        self.db.node_type = "standard"
        self.db.relay_key = None

    @classmethod
    def create_for_device(cls, device, **kwargs):
        """
        Factory method to create a node for a physical device.

        Args:
            device: The physical device object this node represents
            **kwargs: Additional room creation parameters

        Returns:
            MatrixNode: The created node
        """
        device_type = device.typename if hasattr(device, 'typename') else "device"
        room_name = f"Interface: {device.get_display_name(device)}"

        # Create the node
        node = cls.create(room_name, **kwargs)
        node.db.parent_object = device
        node.db.node_type = "device"

        # Set description based on device type
        node.db.desc = f"A sterile virtual space. {device_type.capitalize()} controls shimmer in the void."

        return node

    @classmethod
    def create_for_hub(cls, location, owner=None, **kwargs):
        """
        Factory method to create a hub node for a physical location.

        Args:
            location: The physical room this hub serves
            owner: Optional owner of the hub
            **kwargs: Additional room creation parameters

        Returns:
            MatrixNode: The created hub node
        """
        room_name = f"Node: {location.get_display_name(location)}"

        # Create the node
        node = cls.create(room_name, **kwargs)
        node.db.parent_object = location
        node.db.node_type = "hub"
        node.db.owner = owner

        # Basic hub description
        node.db.desc = "A private network space. Basic security daemons patrol the perimeter."

        return node


class MatrixExit(Exit):
    """
    Exit between Matrix virtual locations.

    These exits connect virtual rooms in the Matrix. They can have different
    behavior than physical exits, including security checks, routing through
    the network, and access logging.

    Attributes:
        security_clearance (int): Clearance level required to traverse (0-10)
        requires_credentials (bool): If True, requires valid credentials to pass
        is_routing (bool): If True, this is a dynamic routing connection (not a permanent exit)
    """

    def at_object_creation(self):
        """Called when the exit is first created."""
        super().at_object_creation()
        self.db.security_clearance = 0
        self.db.requires_credentials = False
        self.db.is_routing = False

    def at_traverse(self, traversing_object, destination):
        """
        Called when someone attempts to traverse this exit.

        Matrix navigation is instantaneous (no walking delay).
        Future implementation will add:
        - Security clearance checks
        - Credential verification
        - ICE alerts on unauthorized access
        - Routing logs
        """
        if not destination:
            super().at_traverse(traversing_object, destination)
            return

        # TODO: Security checks for future implementation
        # if self.db.security_clearance > 0:
        #     # Check traversing_object has required clearance
        #     # Alert ICE if unauthorized
        #     pass

        # Matrix navigation is instantaneous - no delay like physical movement
        direction = (self.key or "away").strip()
        traversing_object.msg(f"You navigate {direction}.")

        # Move immediately
        traversing_object.move_to(destination)
