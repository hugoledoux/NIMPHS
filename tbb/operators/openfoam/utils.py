# <pep8 compliant>
import bpy
from bpy.app.handlers import persistent
from bpy.types import Mesh, Object, Scene, Context

import time
import numpy as np
from typing import Union
from pathlib import Path
from pyvista import OpenFOAMReader, POpenFOAMReader, UnstructuredGrid

from tbb.properties.openfoam.openfoam_clip import TBB_OpenfoamClipProperty
from tbb.operators.utils import remap_array, generate_vertex_colors_groups, generate_vertex_colors, get_collection
from tbb.properties.openfoam.Object.openfoam_streaming_sequence import TBB_OpenfoamStreamingSequenceProperty


def run_one_step_create_mesh_sequence_openfoam(context: Context, current_frame: int, current_time_point: int,
                                               start_time_point: int, user_sequence_name: str):
    """
    Run one step of the 'create mesh sequence' for the OpenFOAM module.

    Args:
        context (Context): context
        current_frame (int): current frame
        current_time_point (int): current time point
        start_time_point (int): start time point
        user_sequence_name (str): user defined sequence name

    Raises:
        error: if something went wrong generating the mesh
    """

    seq_obj_name = user_sequence_name + "_sequence"
    try:
        mesh = generate_mesh_for_sequence(context, current_time_point, name=user_sequence_name)
    except Exception as error:
        raise error

    # First time point, create the sequence object
    if current_time_point == start_time_point:
        # Create the blender object (which will contain the sequence)
        obj = bpy.data.objects.new(user_sequence_name, mesh)
        # The object created from the convert_to_mesh_sequence() method adds
        # "_sequence" at the end of the name
        get_collection("TBB_OpenFOAM", context).objects.link(obj)
        # Convert it to a mesh sequence
        context.view_layer.objects.active = obj

        # TODO: is it possible not to call an operator and do it using functions?
        bpy.ops.ms.convert_to_mesh_sequence()
    else:
        # Add mesh to the sequence
        obj = bpy.data.objects[seq_obj_name]
        context.scene.frame_set(frame=current_frame)

        # Code taken from the Stop-motion-OBJ addon
        # Link: https://github.com/neverhood311/Stop-motion-OBJ/blob/rename-module-name/src/panels.py
        # if the object doesn't have a 'curMeshIdx' fcurve, we can't add a mesh to it
        # TODO: manage the case when there is no 'curMeshIdx'. We may throw an exception or something.
        meshIdxCurve = next(
            (curve for curve in obj.animation_data.action.fcurves if 'curMeshIdx' in curve.data_path), None)

        # add the mesh to the end of the sequence
        meshIdx = add_mesh_to_sequence(obj, mesh)

        # add a new keyframe at this frame number for the new mesh
        obj.mesh_sequence_settings.curMeshIdx = meshIdx
        obj.keyframe_insert(
            data_path='mesh_sequence_settings.curMeshIdx',
            frame=context.scene.frame_current)

        # make the interpolation constant for this keyframe
        newKeyAtFrame = next(
            (keyframe for keyframe in meshIdxCurve.keyframe_points if keyframe.co.x == context.scene.frame_current), None)
        newKeyAtFrame.interpolation = 'CONSTANT'


def generate_mesh_data(file_reader: OpenFOAMReader, time_point: int, triangulate: bool = True,
                       clip: TBB_OpenfoamClipProperty = None,
                       mesh: UnstructuredGrid = None) -> tuple[np.array, np.array, UnstructuredGrid]:
    """
    Generate mesh data for Blender using the given file reader. Applies the clip if defined.
    If 'mesh' is not defined, it will be read from the given OpenFOAMReader (file_reader).

    **Warning**: the given mesh will be modified (clip, extract_surface, triangulation and compute_normals).

    Args:
        file_reader (OpenFOAMReader): OpenFOAM file reader
        time_point (int): time point from which to read data
        triangulate (bool, optional): If `True`, more complex polygons will be broken down into triangles.\
            Defaults to True.
        clip (TBB_OpenfoamClipProperty, optional): clip settings. Defaults to None.
        mesh (UnstructuredGrid, optional): raw mesh. Defaults to None.

    Returns:
        tuple[np.array, np.array, UnstructuredGrid]: vertices, faces and the output mesh (modified)
    """

    # Read data from the given OpenFoam file
    if mesh is None:
        file_reader.set_active_time_point(time_point)
        data = file_reader.read()
        mesh = data["internalMesh"]

    # Apply clip
    if clip is not None and clip.type == "scalar":
        name, value_type = clip.scalar.name.split("@")[0], clip.scalar.name.split("@")[1]
        mesh.set_active_scalars(name=name, preference="point")
        if value_type == "value":
            mesh.clip_scalar(inplace=True, scalars=name, invert=clip.scalar.invert, value=clip.scalar.value)
        if value_type == "vector_value":
            value = np.linalg.norm(clip.scalar.vector_value)
            mesh.clip_scalar(inplace=True, scalars=name, invert=clip.scalar.invert, value=value)
        mesh = mesh.extract_surface(nonlinear_subdivision=0)
    else:
        mesh = mesh.extract_surface(nonlinear_subdivision=0)

    if triangulate:
        mesh.triangulate(inplace=True)
        mesh.compute_normals(inplace=True, consistent_normals=False, split_vertices=True)

    vertices = np.array(mesh.points)

    # Reshape the faces array
    if mesh.is_all_triangles:
        faces = np.array(mesh.faces).reshape(-1, 4)[:, 1:4]
    else:
        faces_indices = np.array(mesh.faces)
        padding, padding_id = 0, 0
        faces = []
        for id in range(mesh.n_faces):
            if padding_id >= faces_indices.size:
                break
            padding = faces_indices[padding_id]
            faces.append(faces_indices[padding_id + 1: padding_id + 1 + padding])
            padding_id = padding_id + (padding + 1)

    return vertices, faces, mesh


def generate_openfoam_streaming_sequence_obj(context: Context, name: str) -> Object:
    """
    Generate the base object for an OpenFOAM 'streaming sequence'.

    Args:
        context (Context): context
        name (str): name of the sequence

    Returns:
        Object: generated object
    """

    # Create the object
    blender_mesh = bpy.data.meshes.new(name + "_sequence_mesh")
    obj = bpy.data.objects.new(name + "_sequence", blender_mesh)

    # Copy settings
    settings = context.scene.tbb.settings.openfoam
    seq_settings = obj.tbb.settings.openfoam.streaming_sequence
    seq_settings.decompose_polyhedra = settings.decompose_polyhedra
    seq_settings.triangulate = settings.triangulate
    seq_settings.case_type = settings.case_type

    # Set clip settings
    seq_settings.clip.type = settings.clip.type
    seq_settings.clip.scalar.list = settings.clip.scalar.list
    seq_settings.clip.scalar.value_ranges = settings.clip.scalar.value_ranges

    # Sometimes, the selected scalar may not correspond to ones available in the EnumProperty.
    # This happens when the selected scalar is not available at time point 0
    # (the EnumProperty only reads data at time point 0 to create the list of available items)
    try:
        seq_settings.clip.scalar.name = settings.clip.scalar.name
    except TypeError as error:
        print("WARNING::setup_openfoam_streaming_sequence_obj: " + str(error))

    seq_settings.clip.scalar.invert = settings.clip.scalar.invert
    # 'value' and 'vector_value' may not be defined, so use .get(prop, default_returned_value)
    seq_settings.clip.scalar["value"] = settings.clip.scalar.get("value", 0.5)
    seq_settings.clip.scalar["vector_value"] = settings.clip.scalar.get("vector_value", (0.5, 0.5, 0.5))

    return obj


def generate_mesh_for_sequence(context: Context, time_point: int, name: str = "TBB") -> Mesh:
    """
    Generate a mesh for an OpenFOAM 'mesh sequence' at the given time point.

    Args:
        context (Context): context
        time_point (int): time point from which to read data
        name (str, optional): name of the output mesh. Defaults to "TBB".

    Raises:
        AttributeError: if the given file does not exist

    Returns:
        Mesh: generate mesh
    """

    settings = context.scene.tbb.settings.openfoam

    # Read data from the given OpenFoam file
    success, file_reader = load_openfoam_file(settings.file_path, settings.case_type, settings.decompose_polyhedra)
    if not success:
        raise AttributeError("The given file does not exist (" + str(settings.file_path) + ")")

    vertices, faces, mesh = generate_mesh_data(
        file_reader, time_point, triangulate=settings.triangulate, clip=settings.clip)

    # Create mesh from python data
    blender_mesh = bpy.data.meshes.new(name + "_mesh")
    blender_mesh.from_pydata(vertices, [], faces)
    # Use fake user so Blender will save our mesh in the .blend file
    blender_mesh.use_fake_user = True

    # Import point data as vertex colors
    if settings.import_point_data:
        res = prepare_openfoam_point_data(mesh, blender_mesh, settings.list_point_data.split(";"), time_point)
        generate_vertex_colors(blender_mesh, *res)

    return blender_mesh


# Code taken from the Stop-motion-OBJ addon
# Link: https://github.com/neverhood311/Stop-motion-OBJ/blob/rename-module-name/src/stop_motion_obj.py
def add_mesh_to_sequence(obj: Object, blender_mesh: Mesh) -> int:
    """
    Add a mesh to an OpenFOAM 'mesh sequence'.

    Args:
        obj (Object): sequence object
        blender_mesh (Mesh): mesh to add to the sequence

    Returns:
        int: mesh id in the sequence
    """

    blender_mesh.inMeshSequence = True
    mss = obj.mesh_sequence_settings
    # add the new mesh to meshNameArray
    newMeshNameElement = mss.meshNameArray.add()
    newMeshNameElement.key = blender_mesh.name_full
    newMeshNameElement.inMemory = True
    # increment numMeshes
    mss.numMeshes = mss.numMeshes + 1
    # increment numMeshesInMemory
    mss.numMeshesInMemory = mss.numMeshesInMemory + 1
    # set initialized to True
    mss.initialized = True
    # set loaded to True
    mss.loaded = True

    return mss.numMeshes - 1


def generate_preview_material(obj: Object, scalar: str, name: str = "TBB_OpenFOAM_preview_material") -> None:
    """
    Generate the preview material (if not generated yet). Update it otherwise (with the new scalar).

    Args:
        obj (Object): object on which to apply the material
        scalar (str): name of the vertex colors group (same as scalar name) to preview
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


def prepare_openfoam_point_data(mesh: UnstructuredGrid, blender_mesh: Mesh, list_point_data: list[str],
                                time_point: int, normalize: str = 'LOCAL') -> tuple[list[dict], dict, int]:
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
        mesh (UnstructuredGrid): mesh data read from the OpenFOAMReader
        blender_mesh (Mesh): mesh on which to add vertex colors
        list_point_data (list[str]): list of point data
        time_point (int): time point from which to read data
        normalize (str, optional): normalize vertex colors, enum in ['LOCAL', 'GLOBAL']. Defaults to 'LOCAL'.

    Returns:
        tuple[list[dict], dict, int]: vertex colors groups, data, number of vertex ids
    """

    # Prepare the mesh to loop over all its triangles
    if len(blender_mesh.loop_triangles) == 0:
        blender_mesh.calc_loop_triangles()
    vertex_ids = np.array([triangle.vertices for triangle in blender_mesh.loop_triangles]).flatten()

    # Filter elements which evaluates to 'False', ex: ''
    list_point_data = list(filter(None, list_point_data))
    # Filter field arrays (check if they exist)
    filtered_variables = []
    for raw_key in list_point_data:
        key = raw_key.split("@")[0]

        try:
            type = raw_key.split("@")[1]
        except BaseException:
            # When the list is given by the user, the type is not provided.
            if key not in mesh.point_data.keys():
                if key != "None":
                    print("WARNING::prepare_openfoam_point_data: the field array named '" +
                          key + "' does not exist (time point = " + str(time_point) + ")")

                continue
            else:
                type = "value" if len(mesh.get_array(key, preference='point').shape) == 1 else "vector_value"

        if key != 'None':
            filtered_variables.append({"name": key, "type": 'SCALAR' if type == "value" else 'VECTOR', "id": key})

    # Prepare data
    prepared_data, data = dict(), None

    for var in filtered_variables:
        data = mesh.get_array(var["id"], preference='point')[vertex_ids]
        if normalize == 'GLOBAL':
            # TODO: implement global 'normalize' (not implemented yet)
            min, max = np.inf, -np.inf
        elif normalize == 'LOCAL':
            min, max = np.min(data), np.max(data)

        data = remap_array(data, in_min=min, in_max=max)
        if var["type"] == 'VECTOR':
            prepared_data[var["id"]] = [data[:, 0], data[:, 1], data[:, 2]]
        elif var["type"] == 'SCALAR':
            prepared_data[var["id"]] = data

    return generate_vertex_colors_groups(filtered_variables), prepared_data, len(vertex_ids)


@persistent
def update_openfoam_streaming_sequences(scene: Scene) -> None:
    """
    App handler appened to the frame_change_pre handlers.
    Updates all the OpenFOAM 'streaming sequences' of the scene.

    Args:
        scene (Scene): scene
    """

    frame = scene.frame_current

    if not scene.tbb.create_sequence_is_running:
        for obj in scene.objects:
            settings = obj.tbb.settings.openfoam.streaming_sequence

            if obj.tbb.is_streaming_sequence and settings.update:
                time_point = frame - settings.frame_start

                if time_point >= 0 and time_point < settings.anim_length:
                    start = time.time()
                    try:
                        update_openfoam_streaming_sequence_mesh(obj, settings, time_point)
                    except Exception as error:
                        print("ERROR::update_openfoam_streaming_sequences: " + settings.name + ", " + str(error))

                    print("Update::OpenFOAM: " + settings.name + ", " + "{:.4f}".format(time.time() - start) + "s")


def update_openfoam_streaming_sequence_mesh(obj: Object, settings: TBB_OpenfoamStreamingSequenceProperty,
                                            time_point: int) -> None:
    """
    Update the mesh of the given OpenFOAM sequence object.

    Args:
        obj (Object): sequence object
        settings (TBB_OpenfoamStreamingSequenceProperty): 'streaming sequence' settings
        time_point (int): time point from which to read data

    Raises:
        OSError: if there was an error reading the file
        ValueError: if the given time point does no exists
    """

    success, file_reader = load_openfoam_file(settings.file_path, settings.case_type, settings.decompose_polyhedra)
    if not success:
        raise OSError("Unable to read the given file")

    # Check if time point is ok
    if time_point >= file_reader.number_time_points:
        raise ValueError("time point '" + str(time_point) + "' does not exist. Available time points: " +
                         str(file_reader.number_time_points))

    vertices, faces, mesh = generate_mesh_data(file_reader, time_point, triangulate=settings.triangulate,
                                               clip=settings.clip)

    blender_mesh = obj.data
    blender_mesh.clear_geometry()
    blender_mesh.from_pydata(vertices, [], faces)

    if settings.shade_smooth:
        blender_mesh.polygons.foreach_set("use_smooth", [True] * len(blender_mesh.polygons))

    # Import point data as vertex colors
    if settings.import_point_data:
        res = prepare_openfoam_point_data(mesh, blender_mesh, settings.list_point_data.split(";"), time_point)
        generate_vertex_colors(blender_mesh, *res)


def load_openfoam_file(file_path: str, case_type: str = 'reconstructed',
                       decompose_polyhedra: bool = False) -> tuple[bool, Union[OpenFOAMReader, POpenFOAMReader]]:
    """
    Load an OpenFOAM file and return the file_reader. Also returns if it succeeded to read.

    Args:
        file_path (str): path to the file
        decompose_polyhedra (bool, optional): whether polyhedra are to be decomposed when read.\
            If `True`, decompose polyhedra into tetrahedra and pyramids. Defaults to `False`.
        case_type (str, optional): indicate whether decomposed mesh or reconstructed mesh should be read. \
            If ``'decomposed'``, decomposed mesh should be read. Defaults to `reconstructed`.

    Returns:
        tuple[bool, OpenFOAMReader]: success, the file reader
    """

    file = Path(file_path)
    if not file.exists():
        return False, None

    if case_type == 1:
        # TODO: does this line can throw exceptions? How to manage errors here?
        file_reader = OpenFOAMReader(file_path)
    else:
        file_reader = POpenFOAMReader(file_path)
        file_reader.case_type = case_type

    file_reader.decompose_polyhedra = decompose_polyhedra
    return True, file_reader