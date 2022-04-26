# <pep8 compliant>
from bpy.types import PropertyGroup
from bpy.props import StringProperty, BoolProperty, EnumProperty, PointerProperty, IntProperty

from ..utils import update_scalar_names
from ..clip import TBB_OpenFOAMClipProperty


settings_dynamic_properties = [
    ("preview_time_point", "Time step used for the preview section"),
    ("start_time_point", "Starting point of the sequence"),
    ("end_time_point", "Ending point of the sequence"),
    ("anim_length", "Length of the animation"),
]


class TBB_OpenFOAMSettings(PropertyGroup):
    # preview_time_point: IntProperty dynamically created

    # start_time_point: IntProperty dynamically created

    # end_time_point: IntProperty dynamically created

    # anim_length: IntProperty dynamically created

    frame_start: IntProperty(
        name="Frame start",
        description="Starting point of the sequence",
        default=1
    )

    file_path: StringProperty(
        name="OpenFoam file path",
        description="Path to the .foam file",
    )

    create_sequence_is_running: BoolProperty(
        name="Create sequence is running",
        description="Describes the state of the create sequence operator",
        default=False,
    )

    preview_point_data: EnumProperty(
        items=update_scalar_names,
        name="Point data",
        description="Name of point data to preview",
    )

    import_point_data: BoolProperty(
        name="Import point data",
        description="Import point data as vertex color groups",
        default=False,
    )

    list_point_data: StringProperty(
        name="Point data list",
        description="List of point data to import as vertex color groups. Separate each with a semicolon",
        default="",
    )

    sequence_type: EnumProperty(
        items=[
            ("mesh_sequence",
             "Mesh sequence",
             "Make a sequence by creating a mesh for each time step (good option for small meshes)"),
            ("streaming_sequence",
             "Streaming sequence",
             "Make a sequence by changing the mesh on each frame change (it only keeps the last created mesh, good option for large meshes)"),
        ],
        name="Sequence type",
        description="Select a sequence type",
    )

    sequence_name: StringProperty(
        name="Sequence name",
        description="Name of the sequence object",
        default="OpenFOAM",
    )

    clip: PointerProperty(type=TBB_OpenFOAMClipProperty)
