# <pep8 compliant>
import bpy
from bpy.app.handlers import persistent
from bpy.types import Mesh, Object, Scene, Context

import logging
log = logging.getLogger(__name__)

import time
import numpy as np
from typing import Union
from pyvista import UnstructuredGrid

from tbb.properties.utils import VariablesInformation
from tbb.properties.openfoam.clip import TBB_OpenfoamClipProperty
from tbb.properties.openfoam.file_data import TBB_OpenfoamFileData
from tbb.properties.shared.point_data_settings import TBB_PointDataSettings
from tbb.operators.utils import remap_array, generate_vertex_colors_groups, generate_vertex_colors
from tbb.operators.openfoam.Scene.openfoam_create_mesh_sequence import TBB_OT_OpenfoamCreateMeshSequence


def generate_openfoam_streaming_sequence_obj(context: Context, obj: Object, name: str) -> Object:
    """
    Generate the base object for an OpenFOAM 'streaming sequence'.

    Args:
        obj (Object): selected object
        name (str): name of the sequence

    Returns:
        Object: generated object
    """

    # Generate new file data
    try:
        file_data = TBB_OpenfoamFileData(obj.tbb.settings.file_path, obj.tbb.settings.openfoam.import_settings)
    except BaseException:
        return None

    # Create the object
    bmesh = bpy.data.meshes.new(name + "_sequence_mesh")
    sequence = bpy.data.objects.new(name + "_sequence", bmesh)
    sequence.tbb.uid = str(time.time())

    # Copy import settings from the selected object
    data = obj.tbb.settings.openfoam.import_settings
    dest = sequence.tbb.settings.openfoam.import_settings

    dest.case_type = data.case_type
    dest.triangulate = data.triangulate
    dest.skip_zero_time = data.skip_zero_time
    dest.decompose_polyhedra = data.decompose_polyhedra

    # Copy file data
    file_data.copy(context.scene.tbb.file_data[obj.tbb.uid])
    context.scene.tbb.file_data[sequence.tbb.uid] = file_data

    return sequence


def generate_preview_material(obj: Object, scalar: str, name: str = "TBB_OpenFOAM_preview_material") -> None:
    """
    Generate or update the preview material.

    Args:
        obj (Object): object on which to apply the material
        scalar (str): name of the vertex colors group to preview
        name (str, optional): name of the preview material. Defaults to "TBB_OpenFOAM_preview_material".
    """

    # Get the preview material
    material = bpy.data.materials.get(name)
    if material is None:
        material = bpy.data.materials.new(name=name)
        material.use_nodes = True

    # Get node tree
    mat_node_tree = material.node_tree
    vertex_color_node = mat_node_tree.nodes.get(name + "_vertex_color")
    if vertex_color_node is None:
        # If the node does not exist, create it and link it to the shader
        vertex_color_node = mat_node_tree.nodes.new(type="ShaderNodeVertexColor")
        vertex_color_node.name = name + "_vertex_color"
        principled_bsdf_node = mat_node_tree.nodes.get("Principled BSDF")
        mat_node_tree.links.new(vertex_color_node.outputs[0], principled_bsdf_node.inputs[0])
        vertex_color_node.location = (-200, 250)

    # Update scalar to preview
    vertex_color_node.layer_name = ""
    if scalar != 'None':
        vertex_color_node.layer_name = scalar
    # Make sure it is the active material
    obj.active_material = material


def prepare_openfoam_point_data(bmesh: Mesh, point_data: Union[TBB_PointDataSettings, str],
                                file_data: TBB_OpenfoamFileData) -> tuple[list[dict], dict, int]:
    """
    Prepare point data for the 'generate_vertex_colors' function.

    .. code-block:: text

        Example of output:
        [
            {'name': 'U.x, U.y, U.z', 'ids': ['U']},
            {'name': 'p, p_rgh, None', 'ids': ['p', 'p_rgh', -1]}
        ]

        {
            'p': array([0.10746115, ..., 0.16983157]),
            'p_rgh': array([0.08247014, ..., 0.12436691]),
            'U': [
                    array([0.9147592,  ..., 0.91178226]),
                    array([0.9147592, ..., 0.91471434]),
                    array([0.9133451, ..., 0.91275126])
                 ]
        }

        137730

    Args:
        bmesh (Mesh): blender mesh
        point_data (Union[TBB_PointDataSettings, str]): point data settings
        file_data (TBB_OpenfoamFileData): file data

    Returns:
        tuple[list[dict], dict, int]: vertex colors groups, color data, number of vertices
    """

    # Prepare the mesh to loop over all its triangles
    if len(bmesh.loop_triangles) == 0:
        bmesh.calc_loop_triangles()

    vertex_ids = np.array([triangle.vertices for triangle in bmesh.loop_triangles]).flatten()

    # Format variables array
    variables, dimensions = [], []
    info = VariablesInformation(point_data if isinstance(point_data, str) else point_data.list)
    for var, type, dim in zip(info.names, info.types, info.dimensions):
        if var != "None":
            variables.append({"name": var, "type": type, "id": var})
            dimensions.append(dim)

    # Prepare data
    prepared_data = dict()
    # If point data is string, then the request comes from the preview panel, so use 'LOCAL' method
    method = 'LOCAL' if isinstance(point_data, str) else point_data.remap_method

    for var, dim in zip(variables, dimensions):
        # Read data
        data = file_data.get_point_data(var["id"])[vertex_ids]

        # Remap data
        if method == 'LOCAL':
            # Update variable information
            file_data.update_var_range(var["name"], var["type"], scope=method)
            var_range = file_data.vars.get(var["id"], prop='RANGE')[method.lower()]

            if var["type"] == 'SCALAR':
                min, max = var_range["min"], var_range["max"]
                prepared_data[var["id"]] = remap_array(np.array(data), in_min=min, in_max=max)

            if var["type"] == 'VECTOR':
                remapped = []
                for i in range(dim):
                    min, max = var_range["min"][i], var_range["max"][i]
                    remapped.append(remap_array(np.array(data[:, i]), in_min=min, in_max=max))

                prepared_data[var["id"]] = remapped

        elif method == 'GLOBAL':

            log.warning("'GLOBAL' remapping method not implemented yet.")
            if var["type"] == 'VECTOR':
                prepared_data[var["id"]] = [data[:, 0], data[:, 1], data[:, 2]]
            elif var["type"] == 'SCALAR':
                prepared_data[var["id"]] = data

    return generate_vertex_colors_groups(variables), prepared_data, len(vertex_ids)


@persistent
def update_openfoam_streaming_sequences(scene: Scene) -> None:
    """
    Update all the OpenFOAM 'streaming sequences' of the scene.

    Args:
        scene (Scene): scene
    """

    frame = scene.frame_current

    if not scene.tbb.m_op_running:
        for obj in scene.objects:
            sequence = obj.tbb.settings.openfoam.s_sequence

            if obj.tbb.is_streaming_sequence and sequence.update:
                # Get file data
                try:
                    scene.tbb.file_data[obj.tbb.uid]
                except KeyError:
                    # Disable update
                    sequence.update = False
                    log.error(f"No file data available for {obj.name}. Disabling update.")
                    return

                time_point = frame - sequence.start

                if time_point >= 0 and time_point < sequence.length:
                    start = time.time()
                    try:
                        update_openfoam_streaming_sequence(scene, obj, time_point)
                    except Exception:
                        log.error(f"Error updating {obj.name}", exc_info=1)

                    log.info(f"Update {obj.name}: " + "{:.4f}".format(time.time() - start) + "s")


def update_openfoam_streaming_sequence(scene: Scene, obj: Object, time_point: int) -> None:
    """
    Update the given OpenFOAM sequence object.

    Args:
        scene (Scene): scene
        obj (Object): sequence object
        time_point (int): time point
    """

    # Get data and settings
    io_settings = obj.tbb.settings.openfoam.import_settings
    file_data = scene.tbb.file_data[obj.tbb.uid]

    if file_data is not None:
        file_data.update_import_settings(io_settings)
        file_data.update_data(time_point)
        vertices, faces, file_data.mesh = generate_mesh_data(file_data, clip=obj.tbb.settings.openfoam.clip)

        bmesh = obj.data
        bmesh.clear_geometry()
        bmesh.from_pydata(vertices, [], faces)

        # Shade smooth
        if obj.tbb.settings.openfoam.s_sequence.shade_smooth:
            bmesh.polygons.foreach_set("use_smooth", [True] * len(bmesh.polygons))

        # Import point data as vertex colors
        point_data = obj.tbb.settings.point_data
        if point_data.import_data and file_data.mesh is not None:
            res = prepare_openfoam_point_data(bmesh, point_data.list, file_data)
            generate_vertex_colors(bmesh, *res)

            # Update information of selected point data
            new_information = VariablesInformation()
            selected = VariablesInformation(point_data.list)
            for var in selected.names:
                new_information.append(data=file_data.vars.get(var))
            point_data.list = new_information.dumps()
