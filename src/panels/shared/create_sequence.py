# <pep8 compliant>
from bpy.types import Panel, Context

from src.panels.utils import get_selected_object
from src.properties.openfoam.temporary_data import TBB_OpenfoamTemporaryData
from src.properties.telemac.temporary_data import TBB_TelemacTemporaryData
from src.properties.openfoam.Scene.openfoam_settings import TBB_OpenfoamSettings
from src.properties.telemac.Scene.telemac_settings import TBB_TelemacSettings


class TBB_CreateSequencePanel(Panel):
    """
    Base UI panel for OpenFOAM and TELEMAC modules.
    Specific settings are added in the classes which derive from this one.
    """

    @classmethod
    def poll(cls, tmp_data: TBB_OpenfoamTemporaryData | TBB_TelemacTemporaryData, context: Context) -> bool:
        """
        If false, hides the panel.

        :param tmp_data: temporary data
        :type tmp_data: TBB_OpenfoamTemporaryData | TBB_TelemacTemporaryData
        :type context: Context
        :rtype: bool
        """

        obj = get_selected_object(context)

        if obj is None:
            return tmp_data.is_ok()
        else:
            return tmp_data.is_ok() and not obj.tbb.is_streaming_sequence

    def draw(self, settings: TBB_OpenfoamSettings | TBB_TelemacSettings, context: Context) -> bool:
        """
        Layout of the panel.

        :param settings: scene settings
        :type settings: TBB_OpenfoamSettings | TBB_TelemacSettings
        :type context: Context
        :return: enable rows
        :rtype: bool
        """

        layout = self.layout

        # Check if we need to lock the ui
        enable_rows = not context.scene.tbb.create_sequence_is_running

        row = layout.row()
        row.enabled = enable_rows
        row.prop(settings, "sequence_type", text="Type")

        if settings.sequence_type == "mesh_sequence":
            row = layout.row()
            row.enabled = enable_rows
            row.prop(settings, '["start_time_point"]', text="Start")
            row = layout.row()
            row.enabled = enable_rows
            row.prop(settings, '["end_time_point"]', text="End")
        elif settings.sequence_type == "streaming_sequence":
            row = layout.row()
            row.enabled = enable_rows
            row.prop(settings, "frame_start", text="Frame start")
            row = layout.row()
            row.enabled = enable_rows
            row.prop(settings, '["anim_length"]', text="Length")
        else:
            row = layout.row()
            row.label(text="Error: unknown sequence type...", icon="ERROR")

        row = layout.row()
        row.enabled = enable_rows
        row.prop(settings, "import_point_data")

        if settings.import_point_data:
            row = layout.row()
            row.enabled = enable_rows
            row.prop(settings, "list_point_data", text="List")

        return enable_rows
