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
"""
Tests for Translator ADM1-ASM1 unit model.

Verified against approximated results results from:

Nopens, I., Batstone, D, Copp, J, Jeppsson, U. Rosen, C., Volcke, E., Alex, J.,
and Vanrolleghem, P.
water Research Vol. 43 pp.1913–1923.
"""

import pytest
from pyomo.environ import (
    ConcreteModel,
    value,
    assert_optimal_termination,
)

from idaes.core import (
    FlowsheetBlock,
    MaterialBalanceType,
    EnergyBalanceType,
    MomentumBalanceType,
)

from pyomo.environ import (
    units,
)

from idaes.core.solvers import get_solver
from idaes.core.util.model_statistics import (
    degrees_of_freedom,
    number_variables,
    number_total_constraints,
    number_unused_variables,
    unused_variables_set,
)

from idaes.core.util.scaling import (
    unscaled_variables_generator,
)
import idaes.logger as idaeslog
from idaes.core.util.testing import initialization_tester

from watertap.unit_models.translators.translator_asm1_adm1 import Translator_ASM1_ADM1
from watertap.property_models.anaerobic_digestion.adm1_properties import (
    ADM1ParameterBlock,
)

from watertap.property_models.activated_sludge.asm1_properties import (
    ASM1ParameterBlock,
)

from watertap.property_models.anaerobic_digestion.adm1_reactions import (
    ADM1ReactionParameterBlock,
)


from pyomo.util.check_units import assert_units_consistent, assert_units_equivalent

# -----------------------------------------------------------------------------
# Get default solver for testing
solver = get_solver()

# -----------------------------------------------------------------------------
@pytest.mark.unit
def test_config():
    m = ConcreteModel()

    m.fs = FlowsheetBlock(dynamic=False)

    m.fs.props_ASM1 = ASM1ParameterBlock()
    m.fs.props_ADM1 = ADM1ParameterBlock()
    m.fs.ADM1_rxn_props = ADM1ReactionParameterBlock(property_package=m.fs.props_ADM1)

    m.fs.unit = Translator_ASM1_ADM1(
        inlet_property_package=m.fs.props_ASM1,
        outlet_property_package=m.fs.props_ADM1,
        reaction_package=m.fs.ADM1_rxn_props,
        has_phase_equilibrium=False,
        outlet_state_defined=True,
    )

    assert len(m.fs.unit.config) == 10

    assert m.fs.unit.config.outlet_state_defined == True
    assert not m.fs.unit.config.dynamic
    assert not m.fs.unit.config.has_holdup
    assert not m.fs.unit.config.has_phase_equilibrium
    assert m.fs.unit.config.inlet_property_package is m.fs.props_ASM1
    assert m.fs.unit.config.outlet_property_package is m.fs.props_ADM1
    assert m.fs.unit.config.reaction_package is m.fs.ADM1_rxn_props


# -----------------------------------------------------------------------------
class TestAsm1Adm1(object):
    @pytest.fixture(scope="class")
    def asmadm(self):
        m = ConcreteModel()

        m.fs = FlowsheetBlock(dynamic=False)

        m.fs.props_ASM1 = ASM1ParameterBlock()
        m.fs.props_ADM1 = ADM1ParameterBlock()
        m.fs.ADM1_rxn_props = ADM1ReactionParameterBlock(
            property_package=m.fs.props_ADM1
        )

        m.fs.unit = Translator_ASM1_ADM1(
            inlet_property_package=m.fs.props_ASM1,
            outlet_property_package=m.fs.props_ADM1,
            reaction_package=m.fs.ADM1_rxn_props,
            has_phase_equilibrium=False,
            outlet_state_defined=True,
        )

        m.fs.unit.inlet.flow_vol.fix(178.4674 * units.m**3 / units.day)
        m.fs.unit.inlet.temperature.fix(308.15 * units.K)
        m.fs.unit.inlet.pressure.fix(1 * units.atm)

        m.fs.unit.inlet.conc_mass_comp[0, "S_I"].fix(28.0665 * units.mg / units.liter)
        m.fs.unit.inlet.conc_mass_comp[0, "S_S"].fix(48.9526 * units.mg / units.liter)
        m.fs.unit.inlet.conc_mass_comp[0, "X_I"].fix(
            10361.7101 * units.mg / units.liter
        )
        m.fs.unit.inlet.conc_mass_comp[0, "X_S"].fix(
            20375.0176 * units.mg / units.liter
        )
        m.fs.unit.inlet.conc_mass_comp[0, "X_BH"].fix(
            10210.0698 * units.mg / units.liter
        )
        m.fs.unit.inlet.conc_mass_comp[0, "X_BA"].fix(553.2808 * units.mg / units.liter)
        m.fs.unit.inlet.conc_mass_comp[0, "X_P"].fix(3204.6601 * units.mg / units.liter)
        m.fs.unit.inlet.conc_mass_comp[0, "S_O"].fix(0.25225 * units.mg / units.liter)
        m.fs.unit.inlet.conc_mass_comp[0, "S_NO"].fix(1.6871 * units.mg / units.liter)
        m.fs.unit.inlet.conc_mass_comp[0, "S_NH"].fix(28.9098 * units.mg / units.liter)
        m.fs.unit.inlet.conc_mass_comp[0, "S_ND"].fix(4.6834 * units.mg / units.liter)
        m.fs.unit.inlet.conc_mass_comp[0, "X_ND"].fix(906.0933 * units.mg / units.liter)
        m.fs.unit.inlet.alkalinity.fix(7.1549 * units.mol / units.m**3)

        return m

    @pytest.mark.build
    @pytest.mark.unit
    def test_build(self, asmadm):

        assert hasattr(asmadm.fs.unit, "inlet")
        assert len(asmadm.fs.unit.inlet.vars) == 5
        assert hasattr(asmadm.fs.unit.inlet, "flow_vol")
        assert hasattr(asmadm.fs.unit.inlet, "conc_mass_comp")
        assert hasattr(asmadm.fs.unit.inlet, "temperature")
        assert hasattr(asmadm.fs.unit.inlet, "pressure")
        assert hasattr(asmadm.fs.unit.inlet, "alkalinity")

        assert hasattr(asmadm.fs.unit, "outlet")
        assert len(asmadm.fs.unit.outlet.vars) == 6
        assert hasattr(asmadm.fs.unit.outlet, "flow_vol")
        assert hasattr(asmadm.fs.unit.outlet, "conc_mass_comp")
        assert hasattr(asmadm.fs.unit.outlet, "temperature")
        assert hasattr(asmadm.fs.unit.outlet, "pressure")
        assert hasattr(asmadm.fs.unit.outlet, "anions")
        assert hasattr(asmadm.fs.unit.outlet, "cations")

        assert number_variables(asmadm) == 133
        assert number_total_constraints(asmadm) == 33

        assert number_unused_variables(asmadm.fs.unit) == 0

    @pytest.mark.component
    def test_units(self, asmadm):
        assert_units_consistent(asmadm)

    @pytest.mark.unit
    def test_dof(self, asmadm):
        assert degrees_of_freedom(asmadm) == 0

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_initialize(self, asmadm):
        initialization_tester(asmadm)

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_solve(self, asmadm):

        asmadm.fs.unit.initialize(outlvl=idaeslog.INFO_HIGH)
        solver = get_solver()
        results = solver.solve(asmadm, tee=True)
        assert_optimal_termination(results)

        asmadm.fs.unit.report()
        asmadm.fs.unit.display()

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_solution(self, asmadm):
        assert pytest.approx(101325.0, rel=1e-3) == value(
            asmadm.fs.unit.outlet.pressure[0]
        )
        assert pytest.approx(308.15, rel=1e-3) == value(
            asmadm.fs.unit.outlet.temperature[0]
        )
        assert pytest.approx(1e-6, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "S_su"]
        )
        assert pytest.approx(0.04388, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "S_aa"]
        )
        assert pytest.approx(1e-6, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "S_fa"]
        )
        assert pytest.approx(1e-6, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "S_va"]
        )
        assert pytest.approx(1e-6, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "S_bu"]
        )
        assert pytest.approx(1e-6, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "S_pro"]
        )
        assert pytest.approx(1e-6, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "S_ac"]
        )
        assert pytest.approx(1e-6, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "S_h2"]
        )
        assert pytest.approx(1e-6, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "S_ch4"]
        )
        assert pytest.approx(0.0858, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "S_IC"]
        )
        assert pytest.approx(0.91266, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "S_IN"]
        )
        assert pytest.approx(0.02806, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "S_I"]
        )

        assert pytest.approx(0.6782, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "X_I"]
        )
        assert pytest.approx(44.0264, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "X_c"]
        )
        assert pytest.approx(1e-6, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "X_ch"]
        )
        assert pytest.approx(1e-6, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "X_pr"]
        )
        assert pytest.approx(1e-6, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "X_li"]
        )
        assert pytest.approx(1e-6, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "X_su"]
        )
        assert pytest.approx(1e-6, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "X_aa"]
        )
        assert pytest.approx(1e-6, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "X_fa"]
        )
        assert pytest.approx(1e-6, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "X_c4"]
        )
        assert pytest.approx(1e-6, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "X_pro"]
        )
        assert pytest.approx(1e-6, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "X_ac"]
        )
        assert pytest.approx(1e-6, rel=1e-3) == value(
            asmadm.fs.unit.outlet.conc_mass_comp[0, "X_h2"]
        )
        assert pytest.approx(0.00715, rel=1e-3) == value(
            asmadm.fs.unit.outlet.cations[0]
        )
        assert pytest.approx(0.06517, rel=1e-3) == value(
            asmadm.fs.unit.outlet.anions[0]
        )

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_conservation(self, asmadm):
        assert (
            abs(
                value(
                    asmadm.fs.unit.inlet.flow_vol[0] * asmadm.fs.props_ADM1.dens_mass
                    - asmadm.fs.unit.outlet.flow_vol[0] * asmadm.fs.props_ASM1.dens_mass
                )
            )
            <= 1e-6
        )

        assert (
            abs(
                value(
                    (
                        asmadm.fs.unit.inlet.flow_vol[0]
                        * asmadm.fs.props_ADM1.dens_mass
                        * asmadm.fs.props_ADM1.cp_mass
                        * (
                            asmadm.fs.unit.inlet.temperature[0]
                            - asmadm.fs.props_ADM1.temperature_ref
                        )
                    )
                    - (
                        asmadm.fs.unit.outlet.flow_vol[0]
                        * asmadm.fs.props_ASM1.dens_mass
                        * asmadm.fs.props_ASM1.cp_mass
                        * (
                            asmadm.fs.unit.outlet.temperature[0]
                            - asmadm.fs.props_ASM1.temperature_ref
                        )
                    )
                )
            )
            <= 1e-6
        )

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_cod(self, asmadm):
        assert (
            abs(
                value(
                    asmadm.fs.unit.CODs[0]
                    - (
                        asmadm.fs.unit.outlet.conc_mass_comp[0, "S_I"]
                        + asmadm.fs.unit.outlet.conc_mass_comp[0, "S_su"]
                        + asmadm.fs.unit.outlet.conc_mass_comp[0, "S_aa"]
                        + asmadm.fs.unit.outlet.conc_mass_comp[0, "S_fa"]
                        + asmadm.fs.unit.outlet.conc_mass_comp[0, "S_va"]
                        + asmadm.fs.unit.outlet.conc_mass_comp[0, "S_bu"]
                        + asmadm.fs.unit.outlet.conc_mass_comp[0, "S_pro"]
                        + asmadm.fs.unit.outlet.conc_mass_comp[0, "S_ac"]
                        + asmadm.fs.unit.outlet.conc_mass_comp[0, "S_h2"]
                        + asmadm.fs.unit.outlet.conc_mass_comp[0, "S_ch4"]
                    )
                )
            )
            <= 1e-5
        )

        assert (
            abs(
                value(
                    asmadm.fs.unit.CODp[0]
                    - (
                        asmadm.fs.unit.outlet.conc_mass_comp[0, "X_I"]
                        + asmadm.fs.unit.outlet.conc_mass_comp[0, "X_su"]
                        + asmadm.fs.unit.outlet.conc_mass_comp[0, "X_aa"]
                        + asmadm.fs.unit.outlet.conc_mass_comp[0, "X_fa"]
                        + asmadm.fs.unit.outlet.conc_mass_comp[0, "X_c4"]
                        + asmadm.fs.unit.outlet.conc_mass_comp[0, "X_pro"]
                        + asmadm.fs.unit.outlet.conc_mass_comp[0, "X_h2"]
                        + asmadm.fs.unit.outlet.conc_mass_comp[0, "X_c"]
                        + asmadm.fs.unit.outlet.conc_mass_comp[0, "X_ch"]
                        + asmadm.fs.unit.outlet.conc_mass_comp[0, "X_pr"]
                        + asmadm.fs.unit.outlet.conc_mass_comp[0, "X_li"]
                    )
                )
            )
            <= 1e-5
        )

        # assert (
        #     abs(
        #         value(
        #             asmadm.fs.unit.TKN[0]
        #             - (asmadm.fs.unit.outlet.conc_mass_comp[0, "S_IN"]
        #             + asmadm.fs.unit.outlet.conc_mass_comp[0, "X_su"]
        #             + asmadm.fs.unit.outlet.conc_mass_comp[0, "X_aa"]
        #             + asmadm.fs.unit.outlet.conc_mass_comp[0, "X_fa"]
        #             + asmadm.fs.unit.outlet.conc_mass_comp[0, "X_c4"]
        #             + asmadm.fs.unit.outlet.conc_mass_comp[0, "X_pro"]
        #             + asmadm.fs.unit.outlet.conc_mass_comp[0, "X_h2"]
        #             + asmadm.fs.unit.outlet.conc_mass_comp[0, "X_c"]
        #             + asmadm.fs.unit.outlet.conc_mass_comp[0, "X_ch"]
        #             + asmadm.fs.unit.outlet.conc_mass_comp[0, "X_pr"]
        #             + asmadm.fs.unit.outlet.conc_mass_comp[0, "X_li"])
        #         )
        #     )
        #     <= 1e-6
        # )
