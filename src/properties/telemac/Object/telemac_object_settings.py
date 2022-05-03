# <pep8 compliant>
from bpy.types import PropertyGroup
from bpy.props import PointerProperty, StringProperty

from .telemac_streaming_sequence import TBB_TelemacStreamingSequenceProperty


class TBB_TelemacObjectSettings(PropertyGroup):
    """
    Data structure which holds object related settings for the TELEMAC module.
    """

    #: bpy.props.StringProperty: Name of the variable used for the 'z-values' of the vertices
    z_name: StringProperty(
        name="Name of z-value",
        description="Name of the variable used for the 'z-values' of the vertices",
        default=""
    )

    #: TBB_TelemacStreamingSequenceProperty: TELEMAC streaming sequence properties
    streaming_sequence: PointerProperty(type=TBB_TelemacStreamingSequenceProperty)