# <pep8 compliant>
from bpy.types import PropertyGroup
from bpy.props import BoolProperty, EnumProperty, PointerProperty, FloatProperty, FloatVectorProperty, StringProperty

from tbb.properties.openfoam.utils import available_point_data, set_clip_values, get_clip_values


class TBB_OpenfoamClipScalarProperty(PropertyGroup):
    """Clip scalar settings."""

    register_cls = True
    is_custom_base_cls = False

    #: bpy.props.FloatProperty: Set the clipping value
    value: FloatProperty(
        name="Value",  # noqa: F821
        description="Set the clipping value",
        default=0.5,
        precision=6,
        step=1,
        set=set_clip_values,
        get=get_clip_values,
    )

    #: bpy.props.FloatProperty: Set the clipping value
    vector_value: FloatVectorProperty(
        name="Value",  # noqa: F821
        description="Set the clipping value",
        default=(0.5, 0.5, 0.5),
        precision=6,
        step=1,
        set=set_clip_values,
        get=get_clip_values,
    )

    #: bpy.props.StringProperty: Save the value ranges of each scalar
    value_ranges: StringProperty(
        name="Value ranges",
        description="Save the value ranges of each scalar",
        default="",
    )

    #: bpy.props.EnumProperty: Name of scalars to clip on
    name: EnumProperty(
        items=available_point_data,
        name="Scalars",  # noqa: F821
        description="Name of scalars to clip on",
    )

    #: bpy.props.StringProperty: Save the list of available scalars
    list: StringProperty(
        name="Clip scalars list",
        description="Save the list of available scalars",
        default="",
    )

    #: bpy.props.BoolProperty: Flag on whether to flip/invert the clip. When True, only the mesh below 'value' will be
    #                          kept. When False, only values above 'value' will be kept
    invert: BoolProperty(
        name="Invert",  # noqa: F821
        description="Flag on whether to flip/invert the clip. When True, only the mesh below 'value' will be kept.\
                     When False, only values above 'value' will be kept",
        default=False,
    )


class TBB_OpenfoamClipProperty(PropertyGroup):
    """Clip settings."""

    register_cls = True
    is_custom_base_cls = False

    #: bpy.props.EnumProperty: Choose the clipping method
    type: EnumProperty(
        items=[
            ("no_clip", "None", "Do not clip"),  # noqa: F821
            ("scalar", "Scalars", "Clip a dataset by a scalar"),  # noqa: F821
            # ("box", "Box", "Clip a dataset by a bounding box defined by the bounds"),
        ],
        name="Type",  # noqa: F821
        description="Choose the clipping method",
        default="no_clip",  # noqa: F821
    )

    #: TBB_OpenfoamClipScalarProperty: Clip scalar settings
    scalar: PointerProperty(type=TBB_OpenfoamClipScalarProperty)
