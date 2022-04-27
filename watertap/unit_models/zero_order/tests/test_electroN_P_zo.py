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
Tests for zero-order electrochemical nutrient recovery model
"""
import pytest
import os

from io import StringIO
from pyomo.environ import (
    Block,
    ConcreteModel,
    Constraint,
    value,
    Var,
    assert_optimal_termination,
    units as pyunits,
)
from pyomo.util.check_units import assert_units_consistent

from idaes.core import FlowsheetBlock
from idaes.core.util import get_solver
from idaes.core.util.model_statistics import degrees_of_freedom
from idaes.core.util.testing import initialization_tester
from idaes.generic_models.costing import UnitModelCostingBlock

from watertap.unit_models.zero_order import ElectroNPZO
from watertap.core.wt_database import Database
from watertap.core.zero_order_properties import WaterParameterBlock
from watertap.core.zero_order_costing import ZeroOrderCosting

solver = get_solver()


class TestElectroNPZO:
    @pytest.fixture(scope="class")
    def model(self):
        m = ConcreteModel()
        m.db = Database()

        m.fs = FlowsheetBlock(default={"dynamic": False})
        m.fs.params = WaterParameterBlock(
            default={"solute_list": ["nitrogen", "phosphorus", "struvite", "foo"]}
        )

        m.fs.unit = ElectroNPZO(
            default={"property_package": m.fs.params, "database": m.db}
        )

        m.fs.unit.inlet.flow_mass_comp[0, "H2O"].fix(1000)
        m.fs.unit.inlet.flow_mass_comp[0, "nitrogen"].fix(1)
        m.fs.unit.inlet.flow_mass_comp[0, "phosphorus"].fix(1)
        m.fs.unit.inlet.flow_mass_comp[0, "struvite"].fix(1)
        m.fs.unit.inlet.flow_mass_comp[0, "foo"].fix(1)

        return m

    @pytest.mark.unit
    def test_build(self, model):
        assert model.fs.unit.config.database == model.db

        assert isinstance(model.fs.unit.magnesium_chloride_dosage, Var)
        assert isinstance(model.fs.unit.electricity, Var)
        assert isinstance(model.fs.unit.energy_electric_flow_mass, Var)
        assert isinstance(model.fs.unit.electricity_consumption, Constraint)

    def test_load_parameters(self, model):
        data = model.db.get_unit_operation_parameters("electroN_P")

        model.fs.unit.load_parameters_from_database(use_default_removal=True)

        assert model.fs.unit.recovery_frac_mass_H2O[0].fixed
        assert (
            model.fs.unit.recovery_frac_mass_H2O[0].value
            == data["recovery_frac_mass_H2O"]["value"]
        )

        for (t, j), v in model.fs.unit.removal_frac_mass_solute.items():
            assert v.fixed
            if j not in data["removal_frac_mass_solute"].keys():
                assert v.value == data["default_removal_frac_mass_solute"]["value"]
            else:
                assert v.value == data["removal_frac_mass_solute"][j]["value"]

        assert model.fs.unit.magnesium_chloride_dosage.fixed
        assert (
            model.fs.unit.magnesium_chloride_dosage.value
            == data["magnesium_chloride_dosage"]["value"]
        )

        assert model.fs.unit.energy_electric_flow_mass.fixed
        assert (
            model.fs.unit.energy_electric_flow_mass.value
            == data["energy_electric_flow_mass"]["value"]
        )

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
        assert_optimal_termination(results)

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_solution(self, model):
        assert pytest.approx(1.004, rel=1e-5) == value(
            model.fs.unit.properties_in[0].flow_vol
        )
        assert pytest.approx(0.99602, rel=1e-5) == value(
            model.fs.unit.properties_in[0].conc_mass_comp["nitrogen"]
        )
        assert pytest.approx(0.99602, rel=1e-5) == value(
            model.fs.unit.properties_in[0].conc_mass_comp["phosphorus"]
        )
        assert pytest.approx(0.99602, rel=1e-5) == value(
            model.fs.unit.properties_in[0].conc_mass_comp["struvite"]
        )

        assert pytest.approx(0.99636, rel=1e-2) == value(
            model.fs.unit.properties_treated[0].flow_vol
        )
        assert pytest.approx(0.17062, rel=1e-5) == value(
            model.fs.unit.properties_treated[0].conc_mass_comp["nitrogen"]
        )
        assert pytest.approx(0.17062, rel=1e-5) == value(
            model.fs.unit.properties_treated[0].conc_mass_comp["phosphorus"]
        )

        assert pytest.approx(0.00183, rel=1e-2) == value(
            model.fs.unit.properties_byproduct[0].flow_vol
        )
        assert pytest.approx(5.4645e-08, rel=1e-5) == value(
            model.fs.unit.properties_byproduct[0].conc_mass_comp["nitrogen"]
        )
        assert pytest.approx(5.4645e-08, rel=1e-5) == value(
            model.fs.unit.properties_byproduct[0].conc_mass_comp["phosphorus"]
        )
        assert pytest.approx(1350.54, abs=1e-5) == value(model.fs.unit.electricity[0])

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_conservation(self, model):
        for j in model.fs.params.component_list:
            assert 1e-6 >= abs(
                value(
                    model.fs.unit.inlet.flow_mass_comp[0, j]
                    + sum(
                        model.fs.unit.generation_rxn_comp[0, r, j]
                        for r in model.fs.unit.reaction_set
                    )
                    - model.fs.unit.treated.flow_mass_comp[0, j]
                    - model.fs.unit.byproduct.flow_mass_comp[0, j]
                )
            )

    @pytest.mark.requires_idaes_solver
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

    Key                                       : Value   : Fixed : Bounds
    Dosage of magnesium chloride per struvite : 0.38800 :  True : (0, None)
                           Electricity Demand :  1350.5 : False : (0, None)
                        Electricity Intensity : 0.20500 :  True : (None, None)
                    Magnesium Chloride Demand :  2556.1 : False : (0, None)
                Reaction Extent [extract_N_P] : 0.83000 : False : (None, None)
                         Solute Removal [foo] :  0.0000 :  True : (0, None)
                    Solute Removal [nitrogen] :  0.0000 :  True : (0, None)
                  Solute Removal [phosphorus] :  0.0000 :  True : (0, None)
                    Solute Removal [struvite] :  1.0000 :  True : (0, None)
                               Water Recovery :  1.0000 :  True : (1e-08, 1.0000001)

------------------------------------------------------------------------------------
    Stream Table
                                    Inlet   Treated   Byproduct
    Volumetric Flowrate            1.0040    0.99636  0.0018300
    Mass Concentration H2O         996.02     998.66 5.4661e-08
    Mass Concentration nitrogen   0.99602    0.17062 5.4645e-08
    Mass Concentration phosphorus 0.99602    0.17062 5.4645e-08
    Mass Concentration struvite   0.99602 1.0037e-10     1000.0
    Mass Concentration foo        0.99602     1.0037 5.4645e-08
====================================================================================
"""

        assert output in stream.getvalue()


def test_costing():
    m = ConcreteModel()
    m.db = Database()

    m.fs = FlowsheetBlock(default={"dynamic": False})

    m.fs.params = WaterParameterBlock(
        default={"solute_list": ["nitrogen", "phosphorus", "struvite", "foo"]}
    )

    source_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "..",
        "..",
        "examples",
        "flowsheets",
        "case_studies",
        "wastewater_resource_recovery",
        "electroN_P",
        "case_1617.yaml",
    )

    m.fs.costing = ZeroOrderCosting(default={"case_study_definition": source_file})

    m.fs.unit = ElectroNPZO(default={"property_package": m.fs.params, "database": m.db})

    m.fs.unit.inlet.flow_mass_comp[0, "H2O"].fix(1000)
    m.fs.unit.inlet.flow_mass_comp[0, "nitrogen"].fix(1)
    m.fs.unit.inlet.flow_mass_comp[0, "phosphorus"].fix(1)
    m.fs.unit.inlet.flow_mass_comp[0, "struvite"].fix(1)
    m.fs.unit.inlet.flow_mass_comp[0, "foo"].fix(1)
    m.fs.unit.load_parameters_from_database(use_default_removal=True)
    assert degrees_of_freedom(m.fs.unit) == 0

    m.fs.unit.costing = UnitModelCostingBlock(
        default={"flowsheet_costing_block": m.fs.costing}
    )

    assert isinstance(m.fs.costing.electroN_P, Block)
    assert isinstance(m.fs.costing.electroN_P.HRT, Var)
    assert isinstance(m.fs.costing.electroN_P.sizing_cost, Var)

    assert isinstance(m.fs.unit.costing.capital_cost, Var)
    assert isinstance(m.fs.unit.costing.capital_cost_constraint, Constraint)

    assert_units_consistent(m.fs)
    assert degrees_of_freedom(m.fs.unit) == 0
    initialization_tester(m)
    results = solver.solve(m)
    assert_optimal_termination(results)

    assert m.fs.unit.electricity[0] in m.fs.costing._registered_flows["electricity"]
    assert (
        m.fs.unit.MgCl2_flowrate[0]
        in m.fs.costing._registered_flows["magnesium_chloride"]
    )
