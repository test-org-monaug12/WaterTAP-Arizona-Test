###############################################################################
# WaterTAP Copyright (c) 2021, The Regents of the University of California,
# through Lawrence Berkeley National Laboratory, Oak Ridge National
# Laboratory, National Renewable Energy Laboratory, and National Energy
# Technology Laboratory (subject to receipt of any required approvals from
# the U.S. Dept. of Energy). All rights reserved.
#
# Please see the files COPYRIGHT.md and LICENSE.md for full copyright and license
# information, respectively. These files are also available online at the URL
# 'https://github.com/watertap-org/watertap/'
#
###############################################################################
import idaes.logger
import pytest
import pyomo.environ as pyo
from pyomo.environ import (
    ConcreteModel,
    TerminationCondition,
    SolverStatus,
    value,
    check_optimal_termination,
)
from pyomo.network import Port

from idaes.core import (
    FlowsheetBlock,
    MaterialBalanceType,
    MomentumBalanceType,
)
from idaes.core.util import get_solver
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
from idaes.core import UnitModelCostingBlock

from watertap.property_models.ion_DSPMDE_prop_pack import (
    DSPMDEParameterBlock,
)
from watertap.unit_models.gac import (
    GAC,
    FilmTransferCoefficientType,
    SurfaceDiffusionCoefficientType,
)
from watertap.costing import WaterTAPCosting

__author__ = "Hunter Barber"

solver = get_solver()


# -----------------------------------------------------------------------------
# Start test class
class TestGACSimplified:
    @pytest.fixture(scope="class")
    def gac_frame_simplified(self):
        m = ConcreteModel()
        m.fs = FlowsheetBlock(default={"dynamic": False})

        m.fs.properties = DSPMDEParameterBlock(
            default={"solute_list": ["DCE"], "mw_data": {"H2O": 18e-3, "DCE": 98.96e-3}}
        )

        m.fs.unit = GAC(
            default={
                "property_package": m.fs.properties,
                "film_transfer_coefficient_type": "fixed",
                "surface_diffusion_coefficient_type": "fixed",
            }
        )

        # feed specifications
        m.fs.unit.process_flow.properties_in[0].pressure.fix(
            101325
        )  # feed pressure [Pa]
        m.fs.unit.process_flow.properties_in[0].temperature.fix(
            273.15 + 25
        )  # feed temperature [K]
        m.fs.unit.process_flow.properties_in[0].flow_mol_phase_comp["Liq", "H2O"].fix(
            55555.55426666667
        )
        m.fs.unit.process_flow.properties_in[0].flow_mol_phase_comp["Liq", "DCE"].fix(
            0.0002344381568310428
        )

        # trial problem from Hand, 1984 for removal of trace DCE
        m.fs.unit.conc_ratio_replace.fix(0.50)
        m.fs.unit.freund_k.fix(37.9e-6 * (1e6**0.8316))
        m.fs.unit.freund_ninv.fix(0.8316)
        m.fs.unit.ebct.fix(300)  # seconds
        m.fs.unit.bed_voidage.fix(0.449)
        m.fs.unit.bed_length.fix(6)  # assumed
        m.fs.unit.particle_porosity.fix(0.5)
        m.fs.unit.particle_dens_app.fix(722)
        m.fs.unit.particle_dia.fix(0.00106)
        m.fs.unit.kf.fix(3.29e-5)
        m.fs.unit.ds.fix(1.77e-13)
        m.fs.unit.a0.fix(3.68421)
        m.fs.unit.a1.fix(13.1579)
        m.fs.unit.b0.fix(0.784576)
        m.fs.unit.b1.fix(0.239663)
        m.fs.unit.b2.fix(0.484422)
        m.fs.unit.b3.fix(0.003206)
        m.fs.unit.b4.fix(0.134987)

        return m

    @pytest.mark.unit
    def test_config_simplified(self, gac_frame_simplified):
        m = gac_frame_simplified
        # check unit config arguments
        assert len(m.fs.unit.config) == 8

        assert not m.fs.unit.config.dynamic
        assert not m.fs.unit.config.has_holdup
        assert m.fs.unit.config.material_balance_type == MaterialBalanceType.useDefault
        assert (
            m.fs.unit.config.momentum_balance_type == MomentumBalanceType.pressureTotal
        )
        assert (
            m.fs.unit.config.film_transfer_coefficient_type
            == FilmTransferCoefficientType.fixed
        )
        assert (
            m.fs.unit.config.surface_diffusion_coefficient_type
            == SurfaceDiffusionCoefficientType.fixed
        )

        assert m.fs.unit.config.property_package is m.fs.properties

        # only designed for single solute and single solvent (water)
        assert len(m.fs.unit.config.property_package.solute_set) == 1
        assert len(m.fs.unit.config.property_package.solvent_set) == 1

    @pytest.mark.unit
    def test_build_simplified(self, gac_frame_simplified):
        m = gac_frame_simplified

        # test ports
        port_lst = ["inlet", "outlet", "adsorbed"]
        for port_str in port_lst:
            port = getattr(m.fs.unit, port_str)
            assert len(port.vars) == 3  # number of state variables for property package
            assert isinstance(port, Port)
        # print(unused_variables_set(m))

        # test statistics
        assert number_variables(m) == 77
        assert number_total_constraints(m) == 45
        assert number_unused_variables(m) == 10  # dens parameters from properties

    @pytest.mark.unit
    def test_dof_simplified(self, gac_frame_simplified):
        m = gac_frame_simplified
        assert degrees_of_freedom(m) == 0

    @pytest.mark.unit
    def test_calculate_scaling_simplified(self, gac_frame_simplified):
        m = gac_frame_simplified

        m.fs.properties.set_default_scaling(
            "flow_mol_phase_comp", 1e-4, index=("Liq", "H2O")
        )
        m.fs.properties.set_default_scaling(
            "flow_mol_phase_comp", 1e4, index=("Liq", "DCE")
        )
        calculate_scaling_factors(m)

        # check that all variables have scaling factors
        unscaled_var_list = list(unscaled_variables_generator(m))
        assert len(unscaled_var_list) == 0

    @pytest.mark.component
    def test_initialize_simplified(self, gac_frame_simplified):
        initialization_tester(gac_frame_simplified)

    @pytest.mark.component
    def test_var_scaling_simplified(self, gac_frame_simplified):
        m = gac_frame_simplified
        badly_scaled_var_lst = list(
            badly_scaled_var_generator(m, large=1e2, small=1e-2)
        )
        for i in badly_scaled_var_lst:
            i[0].pprint()
            print(i[0].name, "scaled to", i[1], "\n")
        assert badly_scaled_var_lst == []

    @pytest.mark.component
    def test_solve_simplified(self, gac_frame_simplified):
        m = gac_frame_simplified
        results = solver.solve(m)

        # Check for optimal solution
        assert results.solver.termination_condition == TerminationCondition.optimal
        assert results.solver.status == SolverStatus.ok

    @pytest.mark.component
    def test_solution_simplified(self, gac_frame_simplified):
        m = gac_frame_simplified

        # Approx data pulled from graph in Hand, 1984 at ~30 days
        # 30 days adjusted to actual solution to account for web plot data extraction error within reason
        assert pytest.approx(29.563, rel=1e-3) == value(m.fs.unit.elap_time) / 24 / 3600

    @pytest.fixture(scope="class")
    def gac_frame_robust(self):
        m = ConcreteModel()
        m.fs = FlowsheetBlock(default={"dynamic": False})

        m.fs.properties = DSPMDEParameterBlock(
            default={"solute_list": ["TCE"], "mw_data": {"H2O": 18e-3, "TCE": 131.4e-3}}
        )

        m.fs.unit = GAC(
            default={
                "property_package": m.fs.properties,
                "film_transfer_coefficient_type": "calculated",
                "surface_diffusion_coefficient_type": "calculated",
            }
        )

        # feed specifications
        m.fs.unit.process_flow.properties_in[0].pressure.fix(
            101325
        )  # feed pressure [Pa]
        m.fs.unit.process_flow.properties_in[0].temperature.fix(
            273.15 + 25
        )  # feed temperature [K]
        m.fs.unit.process_flow.properties_in[0].flow_mol_phase_comp["Liq", "H2O"].fix(
            824.0736620370348
        )
        m.fs.unit.process_flow.properties_in[0].flow_mol_phase_comp["Liq", "TCE"].fix(
            5.644342973110135e-05
        )
        m.fs.unit.process_flow.properties_in[0].flow_vol_phase["Liq"]
        m.fs.unit.process_flow.properties_in[0].conc_mass_phase_comp

        # trial problem from Crittenden, 2012 for removal of TCE
        m.fs.unit.conc_ratio_replace.fix(0.80)
        m.fs.unit.freund_k.fix(1062e-6 * (1e6**0.48))
        m.fs.unit.freund_ninv.fix(0.48)
        m.fs.unit.ebct.fix(10 * 60)
        m.fs.unit.bed_voidage.fix(0.44)
        m.fs.unit.particle_porosity.fix(0.641)
        m.fs.unit.particle_dens_app.fix(803.4)
        m.fs.unit.particle_dia.fix(0.001026)
        m.fs.unit.velocity_sup.fix(5 / 3600)
        m.fs.unit.molal_volume.fix(9.81e-5)
        m.fs.unit.tort.fix(1)
        m.fs.unit.spdfr.fix(1)
        m.fs.unit.sphericity.fix(1.5)
        m.fs.unit.a0.fix(0.8)
        m.fs.unit.a1.fix(0)
        m.fs.unit.b0.fix(0.023)
        m.fs.unit.b1.fix(0.793673)
        m.fs.unit.b2.fix(0.039324)
        m.fs.unit.b3.fix(0.009326)
        m.fs.unit.b4.fix(0.08275)

        return m

    @pytest.mark.unit
    def test_config_robust(self, gac_frame_robust):
        m = gac_frame_robust
        # check unit config arguments
        assert len(m.fs.unit.config) == 8

        assert not m.fs.unit.config.dynamic
        assert not m.fs.unit.config.has_holdup
        assert m.fs.unit.config.material_balance_type == MaterialBalanceType.useDefault
        assert (
            m.fs.unit.config.momentum_balance_type == MomentumBalanceType.pressureTotal
        )
        assert (
            m.fs.unit.config.film_transfer_coefficient_type
            == FilmTransferCoefficientType.calculated
        )
        assert (
            m.fs.unit.config.surface_diffusion_coefficient_type
            == SurfaceDiffusionCoefficientType.calculated
        )

        assert m.fs.unit.config.property_package is m.fs.properties

        # only designed for single solute and single solvent (water)
        assert len(m.fs.unit.config.property_package.solute_set) == 1
        assert len(m.fs.unit.config.property_package.solvent_set) == 1

    @pytest.mark.unit
    def test_build_robust(self, gac_frame_robust):
        m = gac_frame_robust

        # test ports
        port_lst = ["inlet", "outlet", "adsorbed"]
        for port_str in port_lst:
            port = getattr(m.fs.unit, port_str)
            assert len(port.vars) == 3  # number of state variables for property package
            assert isinstance(port, Port)
        # print(unused_variables_set(m))

        # test statistics
        assert number_variables(m) == 84
        assert number_total_constraints(m) == 50
        assert number_unused_variables(m) == 10  # dens parameters from properties

    @pytest.mark.unit
    def test_dof_robust(self, gac_frame_robust):
        m = gac_frame_robust
        assert degrees_of_freedom(m) == 0

    @pytest.mark.unit
    def test_calculate_scaling_robust(self, gac_frame_robust):
        m = gac_frame_robust

        m.fs.properties.set_default_scaling(
            "flow_mol_phase_comp", 1e-2, index=("Liq", "H2O")
        )
        m.fs.properties.set_default_scaling(
            "flow_mol_phase_comp", 1e5, index=("Liq", "TCE")
        )
        calculate_scaling_factors(m)

        # check that all variables have scaling factors
        unscaled_var_list = list(unscaled_variables_generator(m))
        assert len(unscaled_var_list) == 0

    @pytest.mark.component
    def test_initialize_robust(self, gac_frame_robust):
        initialization_tester(gac_frame_robust)

    @pytest.mark.component
    def test_var_scaling_robust(self, gac_frame_robust):
        m = gac_frame_robust
        badly_scaled_var_lst = list(
            badly_scaled_var_generator(m, large=1e2, small=1e-2)
        )
        for i in badly_scaled_var_lst:
            i[0].pprint()
            print(i[0].name, "scaled to", i[1], "\n")
        assert badly_scaled_var_lst == []

    @pytest.mark.component
    def test_solve_robust(self, gac_frame_robust):
        m = gac_frame_robust
        results = solver.solve(m)

        # Check for optimal solution
        assert results.solver.termination_condition == TerminationCondition.optimal
        assert results.solver.status == SolverStatus.ok

    @pytest.mark.component
    def test_solution_robust(self, gac_frame_robust):
        m = gac_frame_robust

        # values calculated independently and near to those reported in Crittenden, 2012
        assert pytest.approx(1.139, rel=1e-3) == value(m.fs.unit.mass_throughput)
        assert pytest.approx(12830000, rel=1e-3) == value(m.fs.unit.elap_time)
        assert pytest.approx(10.68, rel=1e-3) == value(m.fs.unit.bed_area)

    @pytest.mark.component
    def test_reporting_robust(self, gac_frame_robust):
        m = gac_frame_robust
        m.fs.unit.report()

    @pytest.mark.component
    def test_costing_robust(self, gac_frame_robust):
        m = gac_frame_robust

        m.fs.costing = WaterTAPCosting()
        m.fs.costing.base_currency = pyo.units.USD_2020

        m.fs.unit.costing = UnitModelCostingBlock(
            default={
                "flowsheet_costing_block": m.fs.costing,
            },
        )
        m.fs.costing.cost_process()
        results = solver.solve(m)

        # Check for optimal solution
        assert results.solver.termination_condition == TerminationCondition.optimal
        assert results.solver.status == SolverStatus.ok

        # Check for known cost solution of default twin alternating contactors
        assert value(m.fs.costing.gac_num_contactors_op) == 1
        assert value(m.fs.costing.gac_num_contactors_redundant) == 1
        assert pytest.approx(56900.93523, rel=1e-5) == value(
            m.fs.unit.costing.contactor_cost
        )
        assert pytest.approx(4.359114384, rel=1e-5) == value(
            m.fs.unit.costing.adsorbent_unit_cost
        )
        assert pytest.approx(17454.52868, rel=1e-5) == value(
            m.fs.unit.costing.adsorbent_cost
        )
        assert pytest.approx(81692.69369, rel=1e-5) == value(
            m.fs.unit.costing.other_process_cost
        )
        assert pytest.approx(156048.1576, rel=1e-5) == value(
            m.fs.unit.costing.capital_cost
        )
        assert pytest.approx(13535.92023, rel=1e-5) == value(
            m.fs.unit.costing.gac_makeup_cost
        )
        assert pytest.approx(29524.89977, rel=1e-5) == value(
            m.fs.unit.costing.gac_regen_cost
        )
        assert pytest.approx(43060.81999, rel=1e-5) == value(
            m.fs.unit.costing.fixed_operating_cost
        )

    @pytest.mark.component
    def test_costing_modular_contactors_robust(self, gac_frame_robust):
        m = gac_frame_robust

        m.fs.costing = WaterTAPCosting()
        m.fs.costing.base_currency = pyo.units.USD_2020

        m.fs.unit.costing = UnitModelCostingBlock(
            default={
                "flowsheet_costing_block": m.fs.costing,
            },
        )
        m.fs.costing.cost_process()

        m.fs.costing.gac_num_contactors_op.fix(4)
        m.fs.costing.gac_num_contactors_redundant.fix(2)

        results = solver.solve(m)

        # Check for known cost solution when changing volume scale of vessels in parallel
        assert value(m.fs.costing.gac_num_contactors_op) == 4
        assert value(m.fs.costing.gac_num_contactors_redundant) == 2
        assert pytest.approx(89035.16691, rel=1e-5) == value(
            m.fs.unit.costing.contactor_cost
        )
        assert pytest.approx(69693.33132, rel=1e-5) == value(
            m.fs.unit.costing.other_process_cost
        )
        assert pytest.approx(176183.0269, rel=1e-5) == value(
            m.fs.unit.costing.capital_cost
        )

    @pytest.mark.component
    def test_costing_max_gac_ref_robust(self, gac_frame_robust):
        m = gac_frame_robust

        # scale flow up 10x
        m.fs.unit.process_flow.properties_in[0].flow_mol_phase_comp["Liq", "H2O"].fix(
            10 * 824.0736620370348
        )
        m.fs.unit.process_flow.properties_in[0].flow_mol_phase_comp["Liq", "TCE"].fix(
            10 * 5.644342973110135e-05
        )

        m.fs.costing = WaterTAPCosting()
        m.fs.costing.base_currency = pyo.units.USD_2020

        m.fs.unit.costing = UnitModelCostingBlock(
            default={
                "flowsheet_costing_block": m.fs.costing,
            },
        )
        m.fs.costing.cost_process()
        # not necessarily an optimum solution because poor scaling but just checking the conditional
        results = solver.solve(m)

        # Check for bed_mass_gac_cost_ref to be overwritten if bed_mass_gac is greater than bed_mass_gac_cost_max_ref
        assert value(m.fs.unit.bed_mass_gac) > value(m.fs.costing.bed_mass_gac_max_ref)
        assert value(m.fs.unit.costing.bed_mass_gac_ref) == (
            pytest.approx(value(m.fs.costing.bed_mass_gac_max_ref), 1e-5)
        )

    @pytest.fixture(scope="class")
    def gac_frame_robust_upscale(self):
        m = ConcreteModel()
        m.fs = FlowsheetBlock(default={"dynamic": False})

        # specs copied over from gac_frame_robust to isolate testing of 100x upscaled flow
        m.fs.properties = DSPMDEParameterBlock(
            default={"solute_list": ["TCE"], "mw_data": {"H2O": 18e-3, "TCE": 131.4e-3}}
        )

        m.fs.unit = GAC(
            default={
                "property_package": m.fs.properties,
                "film_transfer_coefficient_type": "calculated",
                "surface_diffusion_coefficient_type": "calculated",
            }
        )

        # feed specifications
        m.fs.unit.process_flow.properties_in[0].pressure.fix(
            101325
        )  # feed pressure [Pa]
        m.fs.unit.process_flow.properties_in[0].temperature.fix(
            273.15 + 25
        )  # feed temperature [K]
        m.fs.unit.process_flow.properties_in[0].flow_mol_phase_comp["Liq", "H2O"].fix(
            1000 * 824.0736620370348
        )
        m.fs.unit.process_flow.properties_in[0].flow_mol_phase_comp["Liq", "TCE"].fix(
            1000 * 5.644342973110135e-05
        )
        m.fs.unit.process_flow.properties_in[0].flow_vol_phase["Liq"]
        m.fs.unit.process_flow.properties_in[0].conc_mass_phase_comp

        m.fs.unit.conc_ratio_replace.fix(0.80)
        m.fs.unit.freund_k.fix(1062e-6 * (1e6**0.48))
        m.fs.unit.freund_ninv.fix(0.48)
        m.fs.unit.ebct.fix(10 * 60)
        m.fs.unit.bed_voidage.fix(0.44)
        m.fs.unit.particle_porosity.fix(0.641)
        m.fs.unit.particle_dens_app.fix(803.4)
        m.fs.unit.particle_dia.fix(0.001026)
        m.fs.unit.velocity_sup.fix(5 / 3600)
        m.fs.unit.molal_volume.fix(9.81e-5)
        m.fs.unit.tort.fix(1)
        m.fs.unit.spdfr.fix(1)
        m.fs.unit.sphericity.fix(1.5)
        m.fs.unit.a0.fix(0.8)
        m.fs.unit.a1.fix(0)
        m.fs.unit.b0.fix(0.023)
        m.fs.unit.b1.fix(0.793673)
        m.fs.unit.b2.fix(0.039324)
        m.fs.unit.b3.fix(0.009326)
        m.fs.unit.b4.fix(0.08275)

        m.fs.properties.set_default_scaling(
            "flow_mol_phase_comp", 1e-5, index=("Liq", "H2O")
        )
        m.fs.properties.set_default_scaling(
            "flow_mol_phase_comp", 1e2, index=("Liq", "TCE")
        )
        calculate_scaling_factors(m)

        return m

    @pytest.mark.component
    def test_var_scaling_robust_upscale(self, gac_frame_robust_upscale):
        m = gac_frame_robust_upscale
        initialization_tester(gac_frame_robust_upscale)
        badly_scaled_var_lst = list(
            badly_scaled_var_generator(m, large=1e2, small=1e-2)
        )
        for i in badly_scaled_var_lst:
            i[0].pprint()
            print(i[0].name, "scaled to", i[1], "\n")
        assert badly_scaled_var_lst == []
