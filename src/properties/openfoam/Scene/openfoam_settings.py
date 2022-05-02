# <pep8 compliant>
from bpy.props import EnumProperty, PointerProperty

from ..utils import update_scalar_names
from ..clip import TBB_OpenfoamClipProperty
from ..temporary_data import TBB_OpenfoamTemporaryData
from ...shared.scene_settings import TBB_ModuleSceneSettings


class TBB_OpenfoamSettings(TBB_ModuleSceneSettings):
    """
    OpenFOAM module settings.
    """

    #: TBB_OpenfoamTemporaryData: temporary data
    tmp_data = TBB_OpenfoamTemporaryData()

    #: bpy.types.EnumProperty: Name of point data to preview
    preview_point_data: EnumProperty(
        items=update_scalar_names,
        name="Point data",
        description="Name of point data to preview",
    )

    #: bpy.types.EnumProperty: Select a sequence type
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

    #: TBB_OpenfoamClipProperty: Clip settings
    clip: PointerProperty(type=TBB_OpenfoamClipProperty)
