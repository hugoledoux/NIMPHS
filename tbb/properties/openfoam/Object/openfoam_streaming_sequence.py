# <pep8 compliant>
from bpy.props import PointerProperty

from tbb.properties.shared.module_streaming_sequence_settings import TBB_ModuleStreamingSequenceSettings


class TBB_OpenfoamStreamingSequenceProperty(TBB_ModuleStreamingSequenceSettings):
    """'Streaming sequence' settings for the OpenFOAM module."""

    register_cls = True
    is_custom_base_cls = False
