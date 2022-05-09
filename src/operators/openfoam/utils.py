# <pep8 compliant>
import bpy
from bpy.types import Mesh, Object, Scene, Context
from bpy.app.handlers import persistent

from pyvista import OpenFOAMReader, UnstructuredGrid
from pathlib import Path
import numpy as np
import time

from src.operators.utils import remap_array, generate_vertex_colors_groups
from src.properties.openfoam.Object.openfoam_streaming_sequence import TBB_OpenfoamStreamingSequenceProperty
from src.properties.openfoam.temporary_data import TBB_OpenfoamTemporaryData


def load_openfoam_file(file_path: str, decompose_polyhedra: bool = False) -> tuple[bool, OpenFOAMReader]:
    """
    Load an OpenFOAM file and return the file_reader. Also returns if it succeeded to read.

    :param file_path: path to the file
    :type file_path: str
    :param decompose_polyhedra: Whether polyhedra are to be decomposed when read. If True, decompose polyhedra into tetrahedra and pyramids
    :type decompose_polyhedra: bool, defaults to False
    :return: success, the file reader
    :rtype: tuple[bool, OpenFOAMReader]
    """

    file = Path(file_path)
    if not file.exists():
        return False, None

    # TODO: does this line can throw exceptions? How to manage errors here?
    file_reader = OpenFOAMReader(file_path)
    file_reader.decompose_polyhedra = decompose_polyhedra
    return True, file_reader


def generate_mesh(file_reader: OpenFOAMReader, time_point: int, triangulate: bool = True, clip=None,
                  mesh: UnstructuredGrid = None) -> tuple[np.array, np.array, UnstructuredGrid]:
    """
    Generate mesh data for Blender using the given file reader. Applies the clip if defined.
    If 'mesh' is not defined, it will be read from the given OpenFOAMReader (file_reader).
    **Warning**: the given mesh will be modified (clip, extract_surface, triangulation and compute_normals).

    :param file_reader: OpenFOAM file reader
    :type file_reader: OpenFOAMReader
    :param time_point: time point from which to read data
    :type time_point: int
    :param triangulate: If `True`, more complex polygons will be broken down into triangles
    :type triangulate: bool, defaults to True
    :param clip: clip settings, defaults to None
    :type clip: TBB_OpenfoamClipProperty, optional
    :param mesh: 'raw mesh', defaults to None
    :type mesh: UnstructuredGrid, optional
    :return: vertices, faces and the output mesh (modified)
    :rtype: tuple[np.array, np.array, UnstructuredGrid]
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


def generate_preview_material(obj: Object, scalar: str, name: str = "TBB_OpenFOAM_preview_material") -> None:
    """
    Generate the preview material (if not generated yet). Update it otherwise (with the new scalar).

    :param obj: preview object
    :type obj: Object
    :param scalar: name of the vertex colors group (same as scalar name)
    :type scalar: str
    :param name: name of the preview material, defaults to "TBB_OpenFOAM_preview_material"
    :type name: str, optional
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


def generate_mesh_for_sequence(context: Context, time_point: int, name: str = "TBB") -> Mesh:
    """
    Generate a mesh for an OpenFOAM 'Mesh sequence' at the given time point.

    :type context: Context
    :type time_point: int
    :param name: name of the output mesh, defaults to "TBB"
    :type name: str, optional
    :return: Blender mesh
    :rtype: Mesh
    """

    settings = context.scene.tbb.settings.openfoam

    # Read data from the given OpenFoam file
    success, file_reader = load_openfoam_file(settings.file_path, settings.decompose_polyhedra)
    if not success:
        raise AttributeError("The given file does not exist (" + str(settings.file_path) + ")")

    vertices, faces, mesh = generate_mesh(file_reader, time_point, triangulate=settings.triangulate, clip=settings.clip)

    # Create mesh from python data
    blender_mesh = bpy.data.meshes.new(name + "_mesh")
    blender_mesh.from_pydata(vertices, [], faces)
    # Use fake user so Blender will save our mesh in the .blend file
    blender_mesh.use_fake_user = True

    # Import point data as vertex colors
    if settings.import_point_data:
        blender_mesh = generate_vertex_colors(mesh, blender_mesh, settings.list_point_data.split[";"], time_point)

    return blender_mesh


def prepare_openfoam_point_data(mesh: UnstructuredGrid, blender_mesh: Mesh, list_point_data: list[str],
                                tmp_data: TBB_OpenfoamTemporaryData, time_point: int,
                                normalize: str = 'LOCAL') -> tuple[list[dict], dict, int]:

    # Prepare the mesh to loop over all its triangles
    if len(blender_mesh.loop_triangles) == 0:
        blender_mesh.calc_loop_triangles()
    vertex_ids = np.array([triangle.vertices for triangle in blender_mesh.loop_triangles]).flatten()

    # Filter elements which evaluates to 'False', ex: ''
    print(list_point_data)
    list_point_data = list(filter(None, list_point_data))
    # Filter field arrays (check if they exist)
    filtered_variables = []
    for raw_key in list_point_data:
        key = raw_key.split("@")[0]
        type = raw_key.split("@")[1]
        if key not in mesh.point_data.keys():
            if key != "None":
                print("WARNING::prepare_openfoam_point_data: the field array named '" +
                      key + "' does not exist (time point = " + str(time_point) + ")")
        else:
            filtered_variables.append({"name": key, "type": 'SCALAR' if type == "value" else 'VECTOR', "id": key})

    return generate_vertex_colors_groups(filtered_variables), None, len(vertex_ids)


def generate_vertex_colors(mesh: UnstructuredGrid, blender_mesh: Mesh, list_point_data: str, time_point: int) -> Mesh:
    """
    Generate vertex colors groups for each point data given in the list. The name given to the groups
    are the same as in the list.

    :type mesh: UnstructuredGrid
    :param blender_mesh: mesh which will store the vertex color groups
    :type blender_mesh: Mesh
    :param list_point_data: list of point data (separate each with a ';')
    :type list_point_data: str
    :type time_point: int
    :return: Blender mesh
    :rtype: Mesh
    """

    res = prepare_openfoam_point_data(mesh, blender_mesh, list_point_data, None, time_point)
    print(*res)

    # Prepare the mesh to loop over all its triangles
    if len(blender_mesh.loop_triangles) == 0:
        blender_mesh.calc_loop_triangles()
    vertex_ids = np.array([triangle.vertices for triangle in blender_mesh.loop_triangles]).flatten()

    # Filter field arrays (check if they exist)
    keys = list_point_data.split(";")
    filtered_keys = []
    for raw_key in keys:
        if raw_key != "":
            key = raw_key.split("@")[0]
            if key not in mesh.point_data.keys():
                if key != "None":
                    print("WARNING::generate_vertex_colors: the field array named '" +
                          key + "' does not exist (time point = " + str(time_point) + ")")
            else:
                filtered_keys.append(key)

    for field_array in filtered_keys:
        # Get field array
        colors = mesh.get_array(name=field_array, preference="point")
        # Create new vertex colors array
        vertex_colors = blender_mesh.vertex_colors.new(name=field_array, do_init=True)
        # Normalize data
        colors = remap_array(colors)

        colors = 1.0 - colors
        # 1D scalars
        if len(colors.shape) == 1:
            # Copy values to the B and G color channels
            data = np.tile(np.array([colors[vertex_ids]]).transpose(), (1, 3))
        # 2D scalars
        if len(colors.shape) == 2:
            data = colors[vertex_ids]

        # Add a one for the 'alpha' color channel
        ones = np.ones((len(vertex_ids), 1))
        data = np.hstack((data, ones))

        data = data.flatten()
        vertex_colors.data.foreach_set("color", data)

    return blender_mesh


# Code taken from the Stop-motion-OBJ addon
# Link: https://github.com/neverhood311/Stop-motion-OBJ/blob/rename-module-name/src/stop_motion_obj.py
def add_mesh_to_sequence(obj: Object, blender_mesh: Mesh) -> int:
    """
    Add a mesh to an OpenFOAM 'Mesh sequence'.

    :param obj: sequence object
    :type obj: Object
    :param blender_mesh: mesh to add to the sequence
    :type blender_mesh: Mesh
    :return: mesh id in the sequence
    :rtype: int
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


@persistent
def update_streaming_sequence(scene: Scene) -> None:
    """
    App handler appened to the frame_change_pre handlers. Updates all the OpenFOAM 'Streaming sequences' of the scene.

    :type scene: Scene
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
                        update_sequence_mesh(obj, settings, time_point)
                    except Exception as error:
                        print("ERROR::update_streaming_sequence: " + settings.name + ", " + str(error))

                    print("Update::OpenFOAM: " + settings.name + ", " + "{:.4f}".format(time.time() - start) + "s")


def update_sequence_mesh(obj: Object, settings: TBB_OpenfoamStreamingSequenceProperty, time_point: int) -> None:
    """
    Update the mesh of the given sequence object.

    :param obj: sequence object
    :type obj: Object
    :param settings: streaming sequence settings
    :type settings: TBB_OpenfoamStreamingSequenceProperty
    :param time_point: time point from which to read data
    :type time_point: int
    :raises OSError: if there was an error reading the file
    :raises ValueError: if the given time point does no exists
    """

    # TODO: use load_openfoam_file
    success, file_reader = load_openfoam_file(settings.file_path, settings.decompose_polyhedra)
    if not success:
        raise OSError("Unable to read the given file")

    # Check if time point is ok
    if time_point >= file_reader.number_time_points:
        raise ValueError("time point '" + str(time_point) + "' does not exist. Available time points: " +
                         str(file_reader.number_time_points))

    vertices, faces, mesh = generate_mesh(file_reader, time_point, triangulate=settings.triangulate, clip=settings.clip)

    blender_mesh = obj.data
    blender_mesh.clear_geometry()
    blender_mesh.from_pydata(vertices, [], faces)

    # Import point data as vertex colors
    if settings.import_point_data:
        blender_mesh = generate_vertex_colors(mesh, blender_mesh, settings.list_point_data.split[";"], time_point)


def generate_openfoam_streaming_sequence_obj(context: Context, name: str) -> Object:
    """
    Generate the base object for an OpenFOAM 'streaming sequence'.

    :type context: Context
    :param name: name of the sequence
    :type name: str
    :return: generated object
    :rtype: Object
    """

    # Create the object
    blender_mesh = bpy.data.meshes.new(name + "_sequence_mesh")
    obj = bpy.data.objects.new(name + "_sequence", blender_mesh)

    # Copy settings
    settings = context.scene.tbb.settings.openfoam
    seq_settings = obj.tbb.settings.openfoam.streaming_sequence
    seq_settings.decompose_polyhedra = settings.decompose_polyhedra
    seq_settings.triangulate = settings.triangulate

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
