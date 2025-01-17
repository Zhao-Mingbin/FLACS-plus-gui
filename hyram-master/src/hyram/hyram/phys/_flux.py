import os
import numpy as np
import warnings

from . import _comps, _therm, _flame, _positions
from ..utilities import misc_utils, custom_warnings


def positional_flux_analysis(amb_fluid, rel_fluid, rel_angle, rel_height,
                             site_length, site_width,
                             orif_diams, rel_humid, dis_coeff,
                             rad_src_model, not_nozzle_model,
                             loc_distributions, excl_radius, rand_seed,
                             create_plots=True, chem_file=None, output_dir=None, verbose=False):
    """

    Parameters
    ----------
    amb_fluid : Fluid
        Ambient fluid

    rel_fluid : Fluid
        Release fluid

    rel_angle : float
        angle of release (0 is horizontal) (radians)

    rel_height : float
        vertical starting point (m)

    site_length : float
        Facility length (m)

    site_width : float
        Facility width (m)

    orif_diams : ndarray of floats
        Orifice leak diameters (m), one per leak size

    rel_humid : float
        Relative humidity between 0 and 1

    dis_coeff : float
        Leak discharge coefficient to account for non-plug flow (always <=1, assumed to be 1 for plug flow)

    rad_src_model : {'single', 'multi'}
        Radiative source model

    not_nozzle_model : {'yuce', 'ewan', 'birc', 'bir2', 'molk'}
        Notional nozzle model identifier (i.e. for under-expanded jet zone)

    loc_distributions : list of lists
        Parameters describing positions of workers. See _positions for more information.

    excl_radius : float
        Exclusion radius describing area around source to ignore

    rand_seed : int
        seed for random generation during flame calculation

    create_plots : bool
        Whether plot files should be created

    chem_file : file
        chem object as file, currently unused

    output_dir : str
        file path to directory in which to create files and plots

    Returns : dict
    -------
        fluxes : ndarray
            [kW/m2] Heat flux data for each position, flattened into 1d array

        fluxes_by_pos : ndarray
            [kW/m2] Heat flux data for each position, p x n where p is # positions, n is # leak sizes

        all_iso_fname : list of str
            iso plot filenames for each leak size

        all_t_fname : list of str
            temp plot filenames for each leak size

        all_pos_fname : list of str
            position plot filenames for each leak size

        all_pos_files : list of str
            position plot file paths

        xlocs : ndarray
            x location of positions

        ylocs : ndarray
            y location of positions

        zlocs : ndarray
            z location of positions

        positions : ndarray
            3d positions

    """
    num_sizes = len(orif_diams)
    cons_momentum, notional_noz_t = misc_utils.convert_nozzle_model_to_params(not_nozzle_model, rel_fluid)

    # Generate the positions
    posgen = _positions.PositionGenerator(loc_distributions, excl_radius, rand_seed)
    posgen.gen_positions()
    xlocs = posgen.get_xlocs()
    ylocs = posgen.get_ylocs()
    zlocs = posgen.get_zlocs()
    positions = posgen.locs

    # num_c_atoms = misc_utils.get_num_carbon_atoms_from_species(rel_species)
    num_c_atoms = 0  # NOTE: update this for alt fuels
    chem_obj = _therm.Combustion(amb_fluid.T, nC=num_c_atoms, P=amb_fluid.P)

    # Make some lists to store results for all of the orifice diams
    all_qrads = np.zeros((num_sizes, posgen.totworkers))
    all_iso_fname = []
    all_T_fname = []
    all_pos_fname = []
    all_pos_filepaths = []

    for i in range(len(orif_diams)):
        orif_diam = orif_diams[i]
        iso_fname = 'isoPlot{}'.format(i)
        T_fname = 'Tplot{}'.format(i)

        orifice = _comps.Orifice(orif_diam, Cd=dis_coeff)

        # TODO: pass chem file as well?
        flame = _flame.Flame(rel_fluid, orifice, amb_fluid,
                             nC=num_c_atoms, theta0=rel_angle, y0=rel_height,
                             nn_conserve_momentum=cons_momentum, nn_T=notional_noz_t,
                             chem=chem_obj, verbose=verbose)
        # flame = _flame.Flame(rel_fluid, orifice, amb_fluid)

        flux = flame.generate_positional_flux(xlocs, ylocs, zlocs, rel_humid, rad_src_model)

        # if rad_src_model == 'multi':
        #     flux = flame.Qrad_multi(xlocs, ylocs, zlocs, rel_humid)
        # else:
        #     Lvis = flame.length()
        #     flame_center = np.array([flame.x[np.argmin(np.abs(flame.S - Lvis / 2))],
        #                              flame.y[np.argmin(np.abs(flame.S - Lvis / 2))],
        #                              0])
        #     flux = flame.Qrad_single(xlocs, ylocs, zlocs, flame_center, rel_humid)

        # Each row is the heatflux for all locs for specific leak size
        all_qrads[i, :] = flux
        all_iso_fname.append(iso_fname)
        all_T_fname.append(T_fname)

        # Plot the heatflux position plot
        if create_plots:
            orif_diam = orif_diams[i] * 1000.
            pos_fname = 'positionPlot{}.png'.format(i)
            plot_filepath = os.path.join(output_dir, pos_fname)
            pos_title = '{} mm Leak Size'.format(round(orif_diam, 3))
            posgen.plot_positions(plot_filepath, pos_title, flux, site_length, site_width)
            all_pos_fname.append(pos_fname)
            all_pos_filepaths.append(plot_filepath)

    # Flatten heatflux (all leaksize loc1, then all leaksize loc2, etc)
    # Corresponds to flattening by row which is C-style ordering
    qrads_flat = all_qrads.flatten(order='C')

    result_dict = {
        "fluxes": qrads_flat,
        "fluxes_by_pos": all_qrads,
        "all_iso_fname": all_iso_fname,
        "all_t_fname": all_T_fname,
        "all_pos_fname": all_pos_fname,
        "all_pos_files": all_pos_filepaths,
        "xlocs": xlocs,
        "ylocs": ylocs,
        "zlocs": zlocs,
        "positions": positions,
    }

    return result_dict

