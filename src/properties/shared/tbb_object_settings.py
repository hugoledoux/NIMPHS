# <pep8 compliant>
from bpy.types import PropertyGroup
from bpy.props import PointerProperty, StringProperty

from ..openfoam.Object.openfoam_object_settings import TBB_OpenfoamObjectSettings
from ..telemac.Object.telemac_object_settings import TBB_TelemacObjectSettings


class TBB_ObjectSettings(PropertyGroup):
    """
    Data structure which holds object related settings for all the modules.
    """

    module: StringProperty(
        name="Module name",
        description="Streaming sequence module name, enum in ['None', 'OpenFOAM', 'TELEMAC']",
        default="None",
    )

    #: TBB_OpenfoamObjectSettings: OpenFOAM object properties
    openfoam: PointerProperty(type=TBB_OpenfoamObjectSettings)

    #: TBB_TelemacObjectSettings: TELEMAC object properties
    telemac: PointerProperty(type=TBB_TelemacObjectSettings)