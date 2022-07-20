# <pep8 compliant>
from tbb.properties.shared.module_streaming_sequence_settings import TBB_ModuleStreamingSequenceSettings


class TBB_TelemacStreamingSequenceProperty(TBB_ModuleStreamingSequenceSettings):
    """'streaming sequence' settings for the TELEMAC module."""

    register_cls = True
    is_custom_base_cls = False
