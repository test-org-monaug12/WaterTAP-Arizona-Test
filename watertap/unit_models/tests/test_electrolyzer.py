#################################################################################
# WaterTAP Copyright (c) 2020-2023, The Regents of the University of California,
# through Lawrence Berkeley National Laboratory, Oak Ridge National Laboratory,
# National Renewable Energy Laboratory, and National Energy Technology
# Laboratory (subject to receipt of any required approvals from the U.S. Dept.
# of Energy). All rights reserved.
#
# Please see the files COPYRIGHT.md and LICENSE.md for full copyright and license
# information, respectively. These files are also available online at the URL
# "https://github.com/watertap-org/watertap/"
#################################################################################

import pytest
import pyomo.environ as pyo
from pyomo.environ import (
    ConcreteModel,
    check_optimal_termination,
    value,
)
from pyomo.network import Port
from pyomo.util.check_units import assert_units_consistent

from idaes.core import (
    FlowsheetBlock,
    EnergyBalanceType,
    MaterialBalanceType,
    MomentumBalanceType,
)
from idaes.core.solvers import get_solver
from idaes.core.util.model_statistics import (
    degrees_of_freedom,
    number_variables,
    number_total_constraints,
    number_unused_variables,
)
from idaes.core.util.testing import initialization_tester
from idaes.core.util.scaling import (
    calculate_scaling_factors,
    unscaled_variables_generator,
    badly_scaled_var_generator,
)
from watertap.property_models.multicomp_aq_sol_prop_pack import (
    MCASParameterBlock,
    DiffusivityCalculation,
)
from watertap.unit_models.electrolyzer import Electrolyzer
from watertap.costing import WaterTAPCosting
from idaes.core.util.model_statistics import (
    total_blocks_set,
    report_statistics,
)
from watertap.property_models.anode_reaction import AnodeReactionParameterBlock

__author__ = "Hunter Barber"

solver = get_solver()

# -----------------------------------------------------------------------------
class TestElectrolyzer:
    @pytest.fixture(scope="class")
    def chlor_alkali_elec(self):

        m = ConcreteModel()
        m.fs = FlowsheetBlock(dynamic=False)

        m.fs.properties = MCASParameterBlock(
            solute_list=[
                "NA+",
                "CL-",
                "CL2-v",
                "H2-v",
                "OH-",
            ],
            mw_data={
                "H2O": 0.018015,
                "NA+": 0.022989,
                "CL-": 0.03545,
                "CL2-v": 0.0709,
                "H2-v": 2.016,
                "OH-": 0.017007,
            },
            charge={"NA+": 1, "CL-": -1, "OH-": -1},
        )

        m.fs.unit = Electrolyzer(
            property_package=m.fs.properties,
        )

        # fix property parameters
        m.fs.properties.dens_mass_const = 1200

        # feed specifications
        anolyte_blk = m.fs.unit.anolyte
        catholyte_blk = m.fs.unit.catholyte
        anolyte_blk.properties_in[0].pressure.fix(101325)
        anolyte_blk.properties_in[0].temperature.fix(273.15 + 90)
        anolyte_blk.properties_in[0].flow_mol_phase_comp["Liq", "H2O"].fix(5.551)
        anolyte_blk.properties_in[0].flow_mol_phase_comp["Liq", "NA+"].fix(0.3422)
        anolyte_blk.properties_in[0].flow_mol_phase_comp["Liq", "CL-"].fix(0.3422)
        anolyte_blk.properties_in[0].flow_mol_phase_comp["Liq", "CL2-v"].fix(0)
        anolyte_blk.properties_in[0].flow_mol_phase_comp["Liq", "H2-v"].fix(0)
        anolyte_blk.properties_in[0].flow_mol_phase_comp["Liq", "OH-"].fix(0)
        catholyte_blk.properties_in[0].pressure.fix(101325)
        catholyte_blk.properties_in[0].temperature.fix(273.15 + 90)
        catholyte_blk.properties_in[0].flow_mol_phase_comp["Liq", "H2O"].fix(5.551)
        catholyte_blk.properties_in[0].flow_mol_phase_comp["Liq", "NA+"].fix(1.288)
        catholyte_blk.properties_in[0].flow_mol_phase_comp["Liq", "CL-"].fix(0)
        catholyte_blk.properties_in[0].flow_mol_phase_comp["Liq", "CL2-v"].fix(0)
        catholyte_blk.properties_in[0].flow_mol_phase_comp["Liq", "H2-v"].fix(0)
        catholyte_blk.properties_in[0].flow_mol_phase_comp["Liq", "OH-"].fix(1.288)

        # touch properties
        anolyte_blk.properties_in[0].flow_vol_phase
        anolyte_blk.properties_in[0].conc_mass_phase_comp
        catholyte_blk.properties_in[0].flow_vol_phase
        catholyte_blk.properties_in[0].conc_mass_phase_comp

        # fix variables
        m.fs.unit.current.fix(30000)
        m.fs.unit.current_density.fix(5000)
        m.fs.unit.voltage.fix(2.2)

        # reactions
        m.fs.unit.anode_stoich["Liq", "CL-"].fix(-1)
        m.fs.unit.anode_stoich["Liq", "CL2-v"].fix(1 / 2)
        m.fs.unit.cathode_stoich["Liq", "H2O"].fix(-1)
        m.fs.unit.cathode_stoich["Liq", "H2-v"].fix(1 / 2)
        m.fs.unit.cathode_stoich["Liq", "OH-"].fix(1)

        return m

    @pytest.mark.unit
    def test_general(self, chlor_alkali_elec):

        m = chlor_alkali_elec

        m.fs.unit.pprint()

        assert assert_units_consistent(m) is None
        assert degrees_of_freedom(m) == 0

        prop = m.fs.properties
        prop.set_default_scaling("flow_mol_phase_comp", 1, index=("Liq", "H2O"))
        prop.set_default_scaling("flow_mol_phase_comp", 1, index=("Liq", "NA+"))
        prop.set_default_scaling("flow_mol_phase_comp", 1, index=("Liq", "CL-"))
        prop.set_default_scaling("flow_mol_phase_comp", 1, index=("Liq", "CL2-v"))
        prop.set_default_scaling("flow_mol_phase_comp", 1, index=("Liq", "H2-v"))
        prop.set_default_scaling("flow_mol_phase_comp", 1, index=("Liq", "OH-"))

        calculate_scaling_factors(m)
        initialization_tester(m)
        results = solver.solve(m)

        # Check for optimal solution
        assert check_optimal_termination(results)

        m.fs.unit.display()
