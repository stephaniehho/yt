"""
Magnetic field ... er, fields.



"""

#-----------------------------------------------------------------------------
# Copyright (c) 2013, yt Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
#-----------------------------------------------------------------------------

import numpy as np

from yt.units import dimensions
from yt.units.unit_object import Unit
from yt.units.yt_array import ustack
from yt.utilities.physical_constants import mu_0
from yt.funcs import handle_mks_cgs

from yt.fields.derived_field import \
    ValidateParameter

from .field_plugin_registry import \
    register_field_plugin

from yt.utilities.math_utils import \
    get_sph_theta_component, \
    get_sph_phi_component

mag_factors = {dimensions.magnetic_field_cgs: 4.0*np.pi,
               dimensions.magnetic_field_mks: mu_0}

@register_field_plugin
def setup_magnetic_field_fields(registry, ftype = "gas", slice_info = None):
    unit_system = registry.ds.unit_system

    axis_names = registry.ds.coordinates.axis_order

    if (ftype,"magnetic_field_%s" % axis_names[0]) not in registry:
        return

    u = registry[ftype,"magnetic_field_%s" % axis_names[0]].units

    def _magnetic_field_strength(field, data):
        xm = "relative_magnetic_field_%s" % axis_names[0]
        ym = "relative_magnetic_field_%s" % axis_names[1]
        zm = "relative_magnetic_field_%s" % axis_names[2]

        B2 = (data[ftype, xm])**2 + (data[ftype, ym])**2 + (data[ftype, zm])**2

        return handle_mks_cgs(np.sqrt(B2), field.units)

    registry.add_field((ftype,"magnetic_field_strength"),
                       sampling_type="cell",
                       function=_magnetic_field_strength,
                       validators=[ValidateParameter('bulk_magnetic_field')],
                       units=u)

    def _magnetic_energy(field, data):
        B = data[ftype,"magnetic_field_strength"]
        return 0.5*B*B/mag_factors[B.units.dimensions]

    registry.add_field((ftype, "magnetic_energy"), sampling_type="cell", 
             function=_magnetic_energy,
             units=unit_system["pressure"])

    def _plasma_beta(field,data):
        return data[ftype,'pressure']/data[ftype,'magnetic_energy']

    registry.add_field((ftype, "plasma_beta"), sampling_type="cell", 
             function=_plasma_beta,
             units="")

    def _magnetic_pressure(field,data):
        return data[ftype,'magnetic_energy']

    registry.add_field((ftype, "magnetic_pressure"), sampling_type="cell", 
             function=_magnetic_pressure,
             units=unit_system["pressure"])

    if registry.ds.geometry == "cartesian":
        def _magnetic_field_poloidal(field,data):
            normal = data.get_field_parameter("normal")

            Bfields = ustack([data[ftype, 'relative_magnetic_field_x'],
                              data[ftype, 'relative_magnetic_field_y'],
                              data[ftype, 'relative_magnetic_field_z']])

            theta = data["index", 'spherical_theta']
            phi   = data["index", 'spherical_phi']

            return get_sph_theta_component(Bfields, theta, phi, normal)

        def _magnetic_field_toroidal(field,data):
            normal = data.get_field_parameter("normal")

            Bfields = ustack([data[ftype,'relative_magnetic_field_x'],
                              data[ftype,'relative_magnetic_field_y'],
                              data[ftype,'relative_magnetic_field_z']])

            phi = data["index", 'spherical_phi']
            return get_sph_phi_component(Bfields, phi, normal)

    elif registry.ds.geometry == "cylindrical":
        def _magnetic_field_poloidal(field, data):
            bm = handle_mks_cgs(
                data.get_field_parameter("bulk_magnetic_field"), field.units)
            r = data["index", "r"]
            z = data["index", "z"]
            d = np.sqrt(r*r+z*z)
            rax = axis_names.find('r')
            zax = axis_names.find('z')
            return ((data[ftype, "magnetic_field_r"] - bm[rax])*(r/d) +
                    (data[ftype, "magnetic_field_z"] - bm[zax])*(z/d))

        def _magnetic_field_toroidal(field, data):
            ax = axis_names.find('theta')
            bm = handle_mks_cgs(
                data.get_field_parameter("bulk_magnetic_field"), field.units)
            return data[ftype,"magnetic_field_theta"] - bm[ax]

    elif registry.ds.geometry == "spherical":
        def _magnetic_field_poloidal(field, data):
            ax = axis_names.find('theta')
            bm = handle_mks_cgs(
                data.get_field_parameter("bulk_magnetic_field"), field.units)
            return data[ftype,"magnetic_field_theta"] - bm[ax]

        def _magnetic_field_toroidal(field, data):
            ax = axis_names.find('phi')
            bm = handle_mks_cgs(
                data.get_field_parameter("bulk_magnetic_field"), field.units)
            return data[ftype,"magnetic_field_phi"] - bm[ax]

    else:

        # Unidentified geometry--set to None

        _magnetic_field_toroidal = None
        _magnetic_field_poloidal = None

    registry.add_field((ftype, "magnetic_field_poloidal"),
                       sampling_type="cell",
                       function=_magnetic_field_poloidal,
                       units=u,
                       validators=[ValidateParameter("normal"),
                                   ValidateParameter("bulk_magnetic_field")])

    registry.add_field((ftype, "magnetic_field_toroidal"),
                       sampling_type="cell",
                       function=_magnetic_field_toroidal,
                       units=u,
                       validators=[ValidateParameter("normal"),
                                   ValidateParameter("bulk_magnetic_field")])

    def _alfven_speed(field,data):
        B = data[ftype,'magnetic_field_strength']
        return B/np.sqrt(mag_factors[B.units.dimensions]*data[ftype,'density'])
    registry.add_field((ftype, "alfven_speed"), sampling_type="cell",  function=_alfven_speed,
                       units=unit_system["velocity"])

    def _mach_alfven(field,data):
        return data[ftype,'velocity_magnitude']/data[ftype,'alfven_speed']
    registry.add_field((ftype, "mach_alfven"), sampling_type="cell",  function=_mach_alfven,
                       units="dimensionless")

def setup_magnetic_field_aliases(registry, ds_ftype, ds_fields, ftype="gas"):
    r"""
    This routine sets up special aliases between dataset-specific magnetic fields
    and the default magnetic fields in yt so that unit conversions between different
    unit systems can be handled properly. This is only called from the `setup_fluid_fields`
    method of a frontend's :class:`FieldInfoContainer` instance.

    Parameters
    ----------
    registry : :class:`FieldInfoContainer`
        The field registry that these definitions will be installed into.
    ds_ftype : string
        The field type for the fields we're going to alias, e.g. "flash", "enzo", "athena", etc.
    ds_fields : list of strings
        The fields that will be aliased.
    ftype : string, optional
        The resulting field type of the fields. Default "gas".

    Examples
    --------
    >>> class PlutoFieldInfo(ChomboFieldInfo):
    ...     def setup_fluid_fields(self):
    ...         from yt.fields.magnetic_field import \
    ...             setup_magnetic_field_aliases
    ...         setup_magnetic_field_aliases(self, "chombo", ["bx%s" % ax for ax in [1,2,3]])
    """
    unit_system = registry.ds.unit_system
    ds_fields = [(ds_ftype, fd) for fd in ds_fields]
    if ds_fields[0] not in registry:
        return
    from_units = Unit(registry[ds_fields[0]].units,
                      registry=registry.ds.unit_registry)
    if dimensions.current_mks in unit_system.base_units:
        to_units = unit_system["magnetic_field_mks"]
        equiv = "SI"
    else:
        to_units = unit_system["magnetic_field_cgs"]
        equiv = "CGS"
    if from_units.dimensions == to_units.dimensions:
        convert = lambda x: x.in_units(to_units)
    else:
        convert = lambda x: x.to_equivalent(to_units, equiv)
    def mag_field(fd):
        def _mag_field(field, data):
            return convert(data[fd])
        return _mag_field
    for ax, fd in zip(registry.ds.coordinates.axis_order, ds_fields):
        registry.add_field((ftype,"magnetic_field_%s" % ax),
                           sampling_type="cell", 
                           function=mag_field(fd),
                           units=unit_system[to_units.dimensions])
