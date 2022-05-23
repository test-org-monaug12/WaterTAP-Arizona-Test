###############################################################################
# WaterTAP Copyright (c) 2021, The Regents of the University of California,
# through Lawrence Berkeley National Laboratory, Oak Ridge National
# Laboratory, National Renewable Energy Laboratory, and National Energy
# Technology Laboratory (subject to receipt of any required approvals from
# the U.S. Dept. of Energy). All rights reserved.
#
# Please see the files COPYRIGHT.md and LICENSE.md for full copyright and license
# information, respectively. These files are also available online at the URL
# "https://github.com/watertap-org/watertap/"
#
###############################################################################

# TODO: Load and spot-check base cases corresponding to 2, 3, and 4 stage systems
# for 35g/L, 70g/L, and 125 g/L feed concentrations as base-line coverage for LSRRO flowsheet

# TODO: Maybe we want to randomly generate which of the various test
#       scenarios we run, so we get coverage in expectation.

# TODO: If needed for coverage, *build* and set operating conditions for,
#       but do not *solve*, the cross of all the options.

import glob
import math
import pytest
import os

import pandas as pd

from pyomo.environ import check_optimal_termination, value

from watertap.examples.flowsheets.lsrro.lsrro import (
    ACase,
    BCase,
    ABTradeoff,
    run_lsrro_case,
)

_this_file_path = os.path.dirname(os.path.abspath(__file__))

_input_headers = {
    "cin (kg/m3)": (float, "Cin"),
    "recovery (-)": (float, "water_recovery"),
    "num_stages": (int, "number_of_stages"),
    "A_case": (ACase, "A_case"),
    "B_case": (BCase, "B_case"),
    "AB_Tradeoff": (ABTradeoff, "AB_tradeoff"),
    "AB_gamma_factor": (float, "AB_gamma_factor"),
}

_results_headers = {
    "final brine concentration": "fs.disposal.properties[0].conc_mass_phase_comp[Liq, NaCl]",
    "final perm (ppm)": "fs.final_permeate_concentration",
    "Membrane area": "fs.total_membrane_area",
    "SEC": "fs.costing.specific_energy_consumption",
    "LCOW": "fs.costing.LCOW",
    "LCOW_feed": "fs.costing.LCOW_feed",
    "primary_pump_capex": "fs.costing.primary_pump_capex_lcow",
    "booster_pump_capex": "fs.costing.booster_pump_capex_lcow",
    "erd_capex": "fs.costing.erd_capex_lcow",
    "membrane_capex": "fs.costing.membrane_capex_lcow",
    "indirect_capex": "fs.costing.indirect_capex_lcow",
    "electricity": "fs.costing.electricity_lcow",
    "membrane_replacement": "fs.costing.membrane_replacement_lcow",
    "chem_lab_main": "fs.costing.chemical_labor_maintenance_lcow",
    "pumping_energy_agg_costs": "fs.costing.pumping_energy_aggregate_lcow",
    "membrane_agg_costs": "fs.costing.membrane_aggregate_lcow",
}

_csv_files = glob.glob(
    os.path.join(_this_file_path, "paper_analysis_baselines", "*.csv")
)

_dfs = {os.path.basename(csv_file): pd.read_csv(csv_file) for csv_file in _csv_files}

_test_cases = [
    (csv_file, idx) for csv_file, df in _dfs.items() for idx in range(len(df))
]


@pytest.mark.parametrize("csv_file, row_index", _test_cases)
def test_against_paper_analysis(csv_file, row_index):

    row = _dfs[csv_file].iloc[row_index]
    input_arguments = {
        argument: converter(row[property_name])
        for property_name, (converter, argument) in _input_headers.items()
    }
    number_of_stages = input_arguments["number_of_stages"]
    model, results = run_lsrro_case(**input_arguments)

    if check_optimal_termination(results):
        for property_name, flowsheet_attribute in _results_headers.items():
            assert pytest.approx(
                row["property_name"],
                value(model.find_component(flowsheet_attribute)),
                rtol=1e-4,
            )
    else:
        for property_name in _results_headers:
            assert math.isnan(row["property_name"])
