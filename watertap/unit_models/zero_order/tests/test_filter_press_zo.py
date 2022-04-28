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
Tests for zero-order filter press model
"""
import pytest
from io import StringIO

from pyomo.environ import (
    Block,
    check_optimal_termination,
    ConcreteModel,
    Constraint,
    value,
    Var,
)
from pyomo.util.check_units import assert_units_consistent

from idaes.core import FlowsheetBlock
from idaes.core.util import get_solver
from idaes.core.util.model_statistics import degrees_of_freedom
from idaes.core.util.testing import initialization_tester
from idaes.generic_models.costing import UnitModelCostingBlock

from watertap.unit_models.zero_order import FilterPressZO
from watertap.core.wt_database import Database
from watertap.core.zero_order_properties import WaterParameterBlock
from watertap.core.zero_order_costing import ZeroOrderCosting

solver = get_solver()


class TestFilterPressZO:
    @pytest.fixture(scope="class")
    def model(self):
        m = ConcreteModel()
        m.db = Database()

        m.fs = FlowsheetBlock(default={"dynamic": False})
        m.fs.params = WaterParameterBlock(default={"solute_list": ["tss"]})

        m.fs.unit = FilterPressZO(
            default={"property_package": m.fs.params, "database": m.db}
        )

        m.fs.unit.inlet.flow_mass_comp[0, "H2O"].fix(1)
        m.fs.unit.inlet.flow_mass_comp[0, "tss"].fix(23)

        return m

    @pytest.mark.unit
    def test_build(self, model):
        assert model.fs.unit.config.database is model.db
        assert model.fs.unit._tech_type == "filter_press"
        assert isinstance(model.fs.unit.hours_per_day_operation, Var)
        assert isinstance(model.fs.unit.cycle_time, Var)
        assert isinstance(model.fs.unit.electricity_a_parameter, Var)
        assert isinstance(model.fs.unit.electricity_b_parameter, Var)
        assert isinstance(model.fs.unit.filter_press_capacity, Var)
        assert isinstance(model.fs.unit.fp_electricity, Constraint)
        assert isinstance(model.fs.unit.fp_capacity, Constraint)

    @pytest.mark.component
    def test_load_parameters(self, model):
        data = model.db.get_unit_operation_parameters("filter_press")
        model.fs.unit.load_parameters_from_database()
        assert model.fs.unit.recovery_frac_mass_H2O[0].fixed
        assert model.fs.unit.recovery_frac_mass_H2O[0].value == 0.0001

        for (t, j), v in model.fs.unit.removal_frac_mass_solute.items():
            assert v.fixed
            if j not in data["removal_frac_mass_solute"]:
                assert v.value == data["default_removal_frac_mass_solute"]["value"]
            else:
                assert v.value == data["removal_frac_mass_solute"][j]["value"]

        assert model.fs.unit.hours_per_day_operation[0].fixed
        assert (
            model.fs.unit.hours_per_day_operation[0].value
            == data["hours_per_day_operation"]["value"]
        )
        assert model.fs.unit.cycle_time[0].fixed
        assert model.fs.unit.cycle_time[0].value == data["cycle_time"]["value"]
        assert model.fs.unit.electricity_a_parameter[0].fixed
        assert (
            model.fs.unit.electricity_a_parameter[0].value
            == data["electricity_a_parameter"]["value"]
        )
        assert model.fs.unit.electricity_b_parameter[0].fixed
        assert (
            model.fs.unit.electricity_b_parameter[0].value
            == data["electricity_b_parameter"]["value"]
        )

        for (t, j), v in model.fs.unit.removal_frac_mass_solute.items():
            assert v.fixed
            assert v.value == data["removal_frac_mass_solute"][j]["value"]

    @pytest.mark.component
    def test_degrees_of_freedom(self, model):
        assert degrees_of_freedom(model.fs.unit) == 0

    @pytest.mark.component
    def test_unit_consistency(self, model):
        assert_units_consistent(model.fs.unit)

    @pytest.mark.component
    def test_initialize(self, model):
        initialization_tester(model)

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_solve(self, model):
        results = solver.solve(model)

        # Check for optimal solution
        assert check_optimal_termination(results)

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_solution(self, model):
        assert pytest.approx(0.024, rel=1e-5) == value(
            model.fs.unit.properties_in[0].flow_vol
        )
        assert pytest.approx(41.66666, rel=1e-5) == value(
            model.fs.unit.properties_in[0].conc_mass_comp["H2O"]
        )
        assert pytest.approx(958.33333, rel=1e-5) == value(
            model.fs.unit.properties_in[0].conc_mass_comp["tss"]
        )

        assert pytest.approx(0.000460, rel=1e-3) == value(
            model.fs.unit.properties_treated[0].flow_vol
        )
        assert pytest.approx(0.217344, rel=1e-5) == value(
            model.fs.unit.properties_treated[0].conc_mass_comp["H2O"]
        )
        assert pytest.approx(999.782655, rel=1e-5) == value(
            model.fs.unit.properties_treated[0].conc_mass_comp["tss"]
        )

        assert pytest.approx(0.0235399, rel=1e-5) == value(
            model.fs.unit.properties_byproduct[0].flow_vol
        )
        assert pytest.approx(42.476815, rel=1e-5) == value(
            model.fs.unit.properties_byproduct[0].conc_mass_comp["H2O"]
        )
        assert pytest.approx(957.523184, rel=1e-5) == value(
            model.fs.unit.properties_byproduct[0].conc_mass_comp["tss"]
        )

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_conservation(self, model):
        for j in model.fs.params.component_list:
            assert 1e-6 >= abs(
                value(
                    model.fs.unit.inlet.flow_mass_comp[0, j]
                    - model.fs.unit.treated.flow_mass_comp[0, j]
                    - model.fs.unit.byproduct.flow_mass_comp[0, j]
                )
            )

    @pytest.mark.component
    def test_report(self, model):
        stream = StringIO()

        model.fs.unit.report(ostream=stream)

        output = """
====================================================================================
Unit : fs.unit                                                             Time: 0.0
------------------------------------------------------------------------------------
    Unit Performance

    Variables: 

    Key                         : Value      : Fixed : Bounds
    Filter Press Capacity (ft3) :     9153.6 : False : (None, None)
        Filter Press Power (kW) :     156.61 : False : (0, None)
           Solute Removal [tss] :    0.98000 :  True : (0, None)
                 Water Recovery : 0.00010000 :  True : (0, 1.0000001)

------------------------------------------------------------------------------------
    Stream Table
                             Inlet    Treated   Byproduct
    Volumetric Flowrate    0.024000 0.00046010  0.023540 
    Mass Concentration H2O   41.667    0.21734    42.477 
    Mass Concentration tss   958.33     999.78    957.52 
====================================================================================
"""

        assert output in stream.getvalue()


def test_costing():

    m = ConcreteModel()
    m.db = Database()

    m.fs = FlowsheetBlock(default={"dynamic": False})
    m.fs.params = WaterParameterBlock(default={"solute_list": ["tss"]})

    m.fs.unit = FilterPressZO(
        default={"property_package": m.fs.params, "database": m.db}
    )

    m.fs.unit.inlet.flow_mass_comp[0, "H2O"].fix(1)
    m.fs.unit.inlet.flow_mass_comp[0, "tss"].fix(23)

    m.fs.costing = ZeroOrderCosting()
    m.fs.unit.load_parameters_from_database()

    m.fs.unit.costing = UnitModelCostingBlock(
        default={"flowsheet_costing_block": m.fs.costing}
    )

    assert isinstance(m.fs.costing.filter_press, Block)
    assert isinstance(m.fs.costing.filter_press.capital_a_parameter, Var)
    assert isinstance(m.fs.costing.filter_press.capital_b_parameter, Var)

    assert isinstance(m.fs.unit.costing.capital_cost, Var)
    assert isinstance(m.fs.unit.costing.capital_cost_constraint, Constraint)

    assert_units_consistent(m.fs)
    assert degrees_of_freedom(m.fs.unit) == 0

    assert m.fs.unit.electricity[0] in m.fs.costing._registered_flows["electricity"]
