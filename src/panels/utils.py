# <pep8 compliant>
import bpy
from bpy.types import Context, Object


def sequence_name_already_exist(name: str) -> bool:
    """
    Tell if the given sequence name is already the name of an object. Will look for 'name' + '_sequence'.

    :param user_sequence_name: possible name
    :type user_sequence_name: str
    :rtype: bool
    """

    for object in bpy.data.objects:
        if name + "_sequence" == object.name:
            return True

    return False


def lock_create_operator(settings) -> tuple[bool, str]:
    snae = sequence_name_already_exist(settings.sequence_name)  # snae = sequence_name_already_exist
    snie = settings.sequence_name == "" or settings.sequence_name.isspace()  # snie = sequence name is empty
    if snae:
        message = "Name already taken"
    elif snie:
        message = "Name is empty"
    else:
        message = ""

    return snae or snie, message


def get_selected_object(context: Context) -> Object | None:
    obj = context.active_object
    # Even if no objects are selected, the last selected object remains in the active_objects variable
    if len(context.selected_objects) == 0:
        obj = None

    return obj
