
from typeclasses.matrix.objects import NetworkedObject
from typeclasses.items import Item

class Handset(NetworkedObject, Item) :
  """
  Matrix handset thing. This will have its own ID and act as a device on its own.
  However for interactions many verbs will wind up using the ID of the person rather
  than the ID of this device (unless it's jailbroken and then it'll use the device ID)
  """
  def set_matrix_user_alias(self, MatrixId, NewAlias):
    """
    Set an alias mapping for a given matrix user id.

    This is a stub; game logic will define persistence / ACL behavior later.
    """
    pass

  def get_matrix_user_alias(self, MatrixId):
    """
    Retrieve an alias mapping for a given matrix user id.

    This is a stub; game logic will define persistence / ACL behavior later.
    """
    return None
