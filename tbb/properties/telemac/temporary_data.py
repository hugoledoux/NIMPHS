# <pep8 compliant>
import time
import numpy as np
from typing import Union
import logging
log = logging.getLogger(__name__)

from tbb.properties.telemac.serafin import Serafin
from tbb.properties.shared.temporary_data import TemporaryData
from tbb.properties.telemac.utils import remove_spaces_telemac_var_name
from tbb.properties.utils import VariablesInformation


class TBB_TelemacTemporaryData(TemporaryData):
    """Hold temporary data for the TELEMAC module."""

    # str: name of the module
    module_name = "TELEMAC"
    #: Serafin: TELEMAC file
    file = None
    #: np.ndarray: Vertices of the mesh
    vertices = None
    #: np.ndarray: Faces of the mesh
    faces = None
    #: int: Number of variables
    nb_vars = 0
    #: int: Number of time points
    nb_time_points = 0
    #: VariablesInformation: Information on variables
    vars_info = VariablesInformation()
    #: int: Number of planes
    nb_planes = 0
    #: int: Number of vertices
    nb_vertices = 0
    #: int: Number of triangles
    nb_triangles = 0
    #:  bool: True if the file contains more than one plane
    is_3d = False
    #: np.ndarray
    data = None

    def __init__(self, file_path: str, compute_value_ranges: bool) -> None:
        """
        Init method of the class.

        Args:
            file_path (str): path to the TELEMAC file
            compute_value_ranges (bool): compute value ranges for all the variables
        """

        self.module_name = "TELEMAC"
        self.file = Serafin(file_path, read_time=True)

        self.file.get_2d()  # Read mesh
        self.data = self.file.read(self.file.temps[0])  # Read time step

        self.nb_planes = self.file.nplan
        self.is_3d = self.file.nplan > 1

        self.nb_vertices = self.file.npoin2d if self.is_3d else self.file.npoin
        self.nb_triangles = len(self.file.ikle2d) if self.is_3d else int(len(self.file.ikle) / 3)
        self.nb_vars = self.file.nbvar

        self.nb_time_points = self.file.nb_pdt

        # Construct vertices array
        self.vertices = np.vstack((self.file.x[:self.nb_vertices], self.file.y[:self.nb_vertices])).T

        # Construct faces array
        # Note: '-1' to remove the '+1' offset in the ikle array
        if not self.is_3d:
            self.faces = (np.array(self.file.ikle) - 1).reshape((self.nb_triangles, 3))
        else:
            self.faces = self.file.ikle2d

        # Construct variables information data
        self.vars_info.clear()
        for var_name, id in zip(self.file.nomvar, range(self.nb_vars)):
            # Note: var_name is always 32 chars long with 16 chars for the name and 16 for the unit name
            name = remove_spaces_telemac_var_name(var_name[:16])
            unit = remove_spaces_telemac_var_name(var_name[16:])

            # Compute value ranges
            if compute_value_ranges:
                value_range = self.compute_var_value_range(id)
                value_range = {"global": {"min": value_range["min"], "max": value_range["max"]}}
            else:
                value_range = self.read(0)[id]
                value_range = {"local": {"min": np.min(value_range), "max": np.max(value_range)}}

            self.vars_info.append(name=name, unit=unit, range=value_range)

    def update(self, time_point: int):
        """
        Read data at given time point and compute local value ranges.

        Args:
            time_point (int): time point to read
        """

        self.data = self.read(time_point)

        # Compute 'local' value ranges
        for id in range(self.nb_vars):
            self.vars_info.ranges[id]["local"] = {"min": np.min(self.data[id]), "max": np.max(self.data[id])}

    def read(self, time_point: int = 0) -> np.ndarray:
        """
        Read and return data at the given time point.

        Args:
            time_point (int, optional): time point from which to read data. Defaults to 0.

        Raises:
            ValueError: if the time point does not exist

        Returns:
            np.ndarray: data
        """

        if time_point > self.nb_time_points or time_point < 0:
            raise ValueError("Undefined time point (" + str(time_point) + ")")

        return self.file.read(self.file.temps[time_point])

    def get_data_from_var_name(self, var_name: str, time_point: int, output_shape: str = 'COL') -> np.ndarray:
        """
        Read and return data corresponding to the given variable name.

        Args:
            var_name (str): name of the variable
            time_point (int): time point from which to read data
            output_shape (str, optional): shape of the output, enum in ['COL', 'ROW']. Defaults to 'COL'.

        Raises:
            error: if something went wrong when reading data
            NameError: if the given variable name does not exist

        Returns:
            np.ndarray: data
        """

        try:
            data = self.read(time_point)
        except Exception as error:
            raise error

        # Get the id of the variable name if Serafin.nomvar
        try:
            var_id = self.vars_info.names.index(var_name)
        except ValueError:
            raise NameError("The given variable name '" + str(var_name) + "' is not defined")

        # By default, always output with 'COL' shape, even the given shape is not defined.
        if output_shape not in ['ROW', 'COL']:
            log.warning(f"Unknown output shape {output_shape}. Default to 'COL' mode.")
        if output_shape == 'ROW':
            return data[var_id]
        else:
            return np.array(data[var_id]).reshape(data[var_id].shape[0], 1)

    def get_data_from_possible_var_names(self, possible_var_names: list[str],
                                         time_point: int) -> tuple[np.ndarray, str]:
        """
        Get data from the file and check for every possible given names.

        When one is found, return the associated data.

        Args:
            possible_var_names (list[str]): variable names which could probably be defined in the Serafin file
            time_point (int): time point from which to read data

        Raises:
            error: if an error occurred reading the Serafin file
            NameError: if the possible names are not defined

        Returns:
            tuple[np.ndarray, str]: data, name of the variable which corresponds to the returned data
        """

        z_values = None
        for var_name in possible_var_names:
            try:
                z_values = self.get_data_from_var_name(var_name, time_point)
            except NameError:
                pass
            except Exception as error:
                raise error

            if z_values is not None:
                return z_values, var_name

        if z_values is None:
            raise NameError("Undefined variables " + str(possible_var_names))
        else:
            return z_values, var_name

    def compute_var_value_range(self, var_id: int) -> tuple[float, float]:
        """
        Compute global min / max values of all time points.

        Args:
            var_id (int): variable id

        Returns:
            tuple[float, float]: min, max
        """

        start = time.time()
        min, max = np.inf, -np.inf
        for time_point in range(self.nb_time_points):
            data = self.read(time_point)[var_id]
            new_min, new_max = np.min(data), np.max(data)
            if new_min < min:
                min = new_min
            if new_max > max:
                max = new_max

        self.vars_info.ranges[var_id]["global"] = {"min": min, "max": max}

        message = f"Compute 'global' var value range for {self.vars_info.get(var_id, prop='NAME')}"
        log.info(message + "{:.4f}".format(time.time() - start) + "s")
        return (min, max)

    def get_var_value_range(self, var: Union[int, str]) -> tuple[float, float]:
        """
        Get global min / max values for the given variable.

        Args:
            var (Union[int, str]): variable name or id

        Raises:
            ValueError: if the variable id undefined

        Returns:
            tuple[float, float]: min, max
        """

        if type(var).__name__ == "str":
            var_id = self.vars_info["names"].index(var)
        else:
            var_id = var

        if var_id < 0 or var_id > self.nb_vars:
            raise ValueError("Undefined variable id '" + str(var_id) + "'")

        value_range = self.vars_info["ranges"][var_id]
        if value_range is None:
            value_range = self.compute_var_value_range(var_id)

        return value_range

    def is_ok(self) -> bool:
        """
        Check if temporary data still hold data (data are not None).

        Returns:
            bool: ``True`` if everything is ok
        """
        return self.file is not None and self.vertices is not None and self.faces is not None
