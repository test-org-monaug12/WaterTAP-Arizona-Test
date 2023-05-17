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
__author__ = "Chenyu Wang"

import pyomo.environ as pyo
from pyomo.environ import (
    units,
)
from pyomo.network import Arc, SequentialDecomposition
from idaes.core.util.model_statistics import degrees_of_freedom
from idaes.core.util.initialization import propagate_state
from idaes.core import (
    FlowsheetBlock,
    UnitModelCostingBlock,
)

from idaes.core.solvers import get_solver
import idaes.logger as idaeslog
import idaes.core.util.scaling as iscale
from watertap.unit_models.anaerobic_digestor import AD
from watertap.property_models.anaerobic_digestion.modified_adm1_properties import (
    ModifiedADM1ParameterBlock,
)
from watertap.property_models.anaerobic_digestion.adm1_properties_vapor import (
    ADM1_vaporParameterBlock,
)
from watertap.property_models.anaerobic_digestion.modified_adm1_reactions import (
    ModifiedADM1ReactionParameterBlock,
)
from watertap.property_models.activated_sludge.modified_asm2d_properties import (
    ModifiedASM2dParameterBlock,
)
from watertap.unit_models.translators.translator_adm1_asm2d import Translator_ADM1_ASM2D
from watertap.unit_models.electroNP_ZO import ElectroNPZO
from idaes.core.util.testing import initialization_tester
from idaes.core.util.tables import (
    create_stream_table_dataframe,
    stream_table_dataframe_to_string,
)
from watertap.costing import WaterTAPCosting

# Set up logger
_log = idaeslog.getLogger(__name__)


def automate_rescale_variables(m):
    for var, sv in iscale.badly_scaled_var_generator(m):
        if iscale.get_scaling_factor(var) is None:
            continue
        sf = iscale.get_scaling_factor(var)
        iscale.set_scaling_factor(var, sf / sv)
        iscale.calculate_scaling_factors(m)


def build_flowsheet():
    m = pyo.ConcreteModel()

    m.fs = FlowsheetBlock(dynamic=False)

    m.fs.props_ADM1 = ModifiedADM1ParameterBlock()
    m.fs.props_vap_ADM1 = ADM1_vaporParameterBlock()
    m.fs.rxn_props_ADM1 = ModifiedADM1ReactionParameterBlock(
        property_package=m.fs.props_ADM1
    )
    m.fs.props_ASM2D = ModifiedASM2dParameterBlock(
        additional_solute_list=["S_K", "S_Mg"]
    )
    m.fs.costing = WaterTAPCosting()

    m.fs.AD = AD(
        liquid_property_package=m.fs.props_ADM1,
        vapor_property_package=m.fs.props_vap_ADM1,
        reaction_package=m.fs.rxn_props_ADM1,
        has_heat_transfer=True,
        has_pressure_change=False,
    )

    m.fs.translator_adm1_asm2d = Translator_ADM1_ASM2D(
        inlet_property_package=m.fs.props_ADM1,
        outlet_property_package=m.fs.props_ASM2D,
        reaction_package=m.fs.rxn_props_ADM1,
        has_phase_equilibrium=False,
        outlet_state_defined=True,
    )

    m.fs.electroNP = ElectroNPZO(property_package=m.fs.props_ASM2D)

    m.fs.stream_adm1_translator = Arc(
        source=m.fs.AD.liquid_outlet, destination=m.fs.translator_adm1_asm2d.inlet
    )
    m.fs.stream_translator_electroNP = Arc(
        source=m.fs.translator_adm1_asm2d.outlet, destination=m.fs.electroNP.inlet
    )
    pyo.TransformationFactory("network.expand_arcs").apply_to(m)

    # Feed conditions based on mass balance in Flores-Alsina, where 0 terms are expressed as 1e-9
    m.fs.AD.inlet.flow_vol.fix(
        170 * units.m**3 / units.day
    )  # Double check this value
    m.fs.AD.inlet.temperature.fix(308.15)
    m.fs.AD.inlet.pressure.fix(101325)

    m.fs.AD.inlet.conc_mass_comp[0, "S_su"].fix(0.034597)
    m.fs.AD.inlet.conc_mass_comp[0, "S_aa"].fix(0.015037)
    m.fs.AD.inlet.conc_mass_comp[0, "S_fa"].fix(1e-6)
    m.fs.AD.inlet.conc_mass_comp[0, "S_va"].fix(1e-6)
    m.fs.AD.inlet.conc_mass_comp[0, "S_bu"].fix(1e-6)
    m.fs.AD.inlet.conc_mass_comp[0, "S_pro"].fix(1e-6)
    m.fs.AD.inlet.conc_mass_comp[0, "S_ac"].fix(0.025072)
    m.fs.AD.inlet.conc_mass_comp[0, "S_h2"].fix(1e-6)
    m.fs.AD.inlet.conc_mass_comp[0, "S_ch4"].fix(1e-6)
    m.fs.AD.inlet.conc_mass_comp[0, "S_IC"].fix(0.34628)
    m.fs.AD.inlet.conc_mass_comp[0, "S_IN"].fix(0.60014)
    m.fs.AD.inlet.conc_mass_comp[0, "S_IP"].fix(0.22677)
    m.fs.AD.inlet.conc_mass_comp[0, "S_I"].fix(0.026599)

    m.fs.AD.inlet.conc_mass_comp[0, "X_ch"].fix(7.3687)
    m.fs.AD.inlet.conc_mass_comp[0, "X_pr"].fix(7.7308)
    m.fs.AD.inlet.conc_mass_comp[0, "X_li"].fix(10.3288)
    m.fs.AD.inlet.conc_mass_comp[0, "X_su"].fix(1e-6)
    m.fs.AD.inlet.conc_mass_comp[0, "X_aa"].fix(1e-6)
    m.fs.AD.inlet.conc_mass_comp[0, "X_fa"].fix(1e-6)
    m.fs.AD.inlet.conc_mass_comp[0, "X_c4"].fix(1e-6)
    m.fs.AD.inlet.conc_mass_comp[0, "X_pro"].fix(1e-6)
    m.fs.AD.inlet.conc_mass_comp[0, "X_ac"].fix(1e-6)
    m.fs.AD.inlet.conc_mass_comp[0, "X_h2"].fix(1e-6)
    m.fs.AD.inlet.conc_mass_comp[0, "X_I"].fix(12.7727)
    m.fs.AD.inlet.conc_mass_comp[0, "X_PHA"].fix(0.0022493)
    m.fs.AD.inlet.conc_mass_comp[0, "X_PP"].fix(1.04110)
    m.fs.AD.inlet.conc_mass_comp[0, "X_PAO"].fix(3.4655)
    m.fs.AD.inlet.conc_mass_comp[0, "S_K"].fix(0.02268)
    m.fs.AD.inlet.conc_mass_comp[0, "S_Mg"].fix(0.02893)

    m.fs.AD.inlet.cations[0].fix(0.04)
    m.fs.AD.inlet.anions[0].fix(0.02)

    m.fs.AD.volume_liquid.fix(3400)
    m.fs.AD.volume_vapor.fix(300)
    m.fs.AD.liquid_outlet.temperature.fix(308.15)

    # ElectroNP
    m.fs.electroNP.energy_electric_flow_mass.fix(0.044 * units.kWh / units.kg)
    m.fs.electroNP.magnesium_chloride_dosage.fix(0.388)

    # scaling
    for var in m.fs.component_data_objects(pyo.Var, descend_into=True):
        if "flow_vol" in var.name:
            iscale.set_scaling_factor(var, 1e3)
        if "temperature" in var.name:
            iscale.set_scaling_factor(var, 1e-1)
        if "pressure" in var.name:
            iscale.set_scaling_factor(var, 1e-3)
        if "alkalinity" in var.name:
            iscale.set_scaling_factor(var, 1e-1)
        if "conc_mass_comp" in var.name:
            iscale.set_scaling_factor(var, 1e1)
        if "conc_mass_comp[S_IN]" in var.name:
            iscale.set_scaling_factor(var, 1)
        if "conc_mass_comp[S_IP]" in var.name:
            iscale.set_scaling_factor(var, 1)
        if "conc_mass_comp[S_PO4]" in var.name:
            iscale.set_scaling_factor(var, 1e-1)
        if "conc_mass_comp[S_NH4]" in var.name:
            iscale.set_scaling_factor(var, 1e1)
        if "conc_mass_comp[S_F]" in var.name:
            iscale.set_scaling_factor(var, 1e-1)
        if "conc_mass_comp[X_I]" in var.name:
            iscale.set_scaling_factor(var, 1e-1)
        if "conc_mass_comp[S_O2]" in var.name:
            iscale.set_scaling_factor(var, 1e3)
        if "conc_mass_comp[S_N2]" in var.name:
            iscale.set_scaling_factor(var, 1e3)
        if "conc_mass_comp[S_NO3]" in var.name:
            iscale.set_scaling_factor(var, 1e3)
        if "conc_mass_comp[X_H]" in var.name:
            iscale.set_scaling_factor(var, 1e3)
        if "conc_mass_comp[X_PAO]" in var.name:
            iscale.set_scaling_factor(var, 1e3)
        if "conc_mass_comp[X_AUT]" in var.name:
            iscale.set_scaling_factor(var, 1e3)
        if "conc_mass_comp[X_MeOH]" in var.name:
            iscale.set_scaling_factor(var, 1e3)
        if "conc_mass_comp[X_MeP]" in var.name:
            iscale.set_scaling_factor(var, 1e3)
        if "conc_mass_comp[X_TSS]" in var.name:
            iscale.set_scaling_factor(var, 1e3)
        if "conc_mass_comp[S_ch4]" in var.name:
            iscale.set_scaling_factor(var, 1e3)
        if "conc_mass_comp[X_su]" in var.name:
            iscale.set_scaling_factor(var, 1e3)
        if "conc_mass_comp[X_fa]" in var.name:
            iscale.set_scaling_factor(var, 1e3)
        if "conc_mass_comp[X_c4]" in var.name:
            iscale.set_scaling_factor(var, 1e3)
        if "conc_mass_comp[X_pro]" in var.name:
            iscale.set_scaling_factor(var, 1e3)
        if "conc_mass_comp[X_ac]" in var.name:
            iscale.set_scaling_factor(var, 1e3)
        if "conc_mass_comp[X_h2]" in var.name:
            iscale.set_scaling_factor(var, 1e3)

    # m.fs.props_ASM2D.set_default_scaling("pressure", 1e-3)
    # m.fs.props_ASM2D.set_default_scaling("temperature", 1e-1)
    # m.fs.props_ASM2D.set_default_scaling("flow_vol", 1e3)
    # m.fs.props_ASM2D.set_default_scaling("conc_mass_comp", 1e3, index=("S_O2"))
    # m.fs.props_ASM2D.set_default_scaling("conc_mass_comp", 1e3, index=("S_N2"))
    # m.fs.props_ASM2D.set_default_scaling("conc_mass_comp", 1e1, index=("S_NH4"))
    # m.fs.props_ASM2D.set_default_scaling("conc_mass_comp", 1e3, index=("S_NO3"))
    # m.fs.props_ASM2D.set_default_scaling("conc_mass_comp", 1e-1, index=("S_PO4"))
    # m.fs.props_ASM2D.set_default_scaling("conc_mass_comp", 1e-1, index=("S_F"))
    # m.fs.props_ASM2D.set_default_scaling("conc_mass_comp", 1e1, index=("S_A"))
    # m.fs.props_ASM2D.set_default_scaling("conc_mass_comp", 1e1, index=("S_I"))
    # m.fs.props_ASM2D.set_default_scaling("conc_mass_comp", 1e-1, index=("X_I"))
    # m.fs.props_ASM2D.set_default_scaling("conc_mass_comp", 1e1, index=("X_S"))
    # m.fs.props_ASM2D.set_default_scaling("conc_mass_comp", 1e3, index=("X_H"))
    # m.fs.props_ASM2D.set_default_scaling("conc_mass_comp", 1e3, index=("X_PAO"))
    # m.fs.props_ASM2D.set_default_scaling("conc_mass_comp", 1e1, index=("X_PP"))
    # m.fs.props_ASM2D.set_default_scaling("conc_mass_comp", 1e1, index=("X_PHA"))
    # m.fs.props_ASM2D.set_default_scaling("conc_mass_comp", 1e3, index=("X_AUT"))
    # m.fs.props_ASM2D.set_default_scaling("conc_mass_comp", 1e3, index=("X_MeOH"))
    # m.fs.props_ASM2D.set_default_scaling("conc_mass_comp", 1e3, index=("X_MeP"))
    # m.fs.props_ASM2D.set_default_scaling("conc_mass_comp", 1e3, index=("X_TSS"))
    # m.fs.props_ASM2D.set_default_scaling("conc_mass_comp", 1e1, index=("S_K"))
    # m.fs.props_ASM2D.set_default_scaling("conc_mass_comp", 1e1, index=("S_Mg"))
    # m.fs.props_ASM2D.set_default_scaling("alkalinity", 1e-1)

    iscale.calculate_scaling_factors(m)

    # TO DO: Fix initialization
    # m.fs.AD.initialize(outlvl=idaeslog.INFO_HIGH, optarg={"bound_push": 1e-2})
    # propagate_state(m.fs.stream_adm1_translator)
    # m.fs.translator_adm1_asm2d.initialize(outlvl=idaeslog.INFO_HIGH, optarg={"bound_push": 1e-2})
    # propagate_state(m.fs.stream_translator_electroNP)
    # m.fs.electroNP.initialize(outlvl=idaeslog.INFO_HIGH, optarg={"bound_push": 1e-2})
    #
    # solver = get_solver(options={"bound_push": 1e-2})

    # Apply sequential decomposition - 1 iteration should suffice
    seq = SequentialDecomposition()
    seq.options.tear_set = []
    seq.options.iterLim = 1

    def function(unit):
        unit.initialize(outlvl=idaeslog.INFO, optarg={"bound_push": 1e-2})
        badly_scaled_vars = list(iscale.badly_scaled_var_generator(unit))
        if len(badly_scaled_vars) > 0:
            [print(i[0]) for i in badly_scaled_vars]
            automate_rescale_variables(unit)

    seq.run(m, function)

    solver = get_solver(options={"bound_push": 1e-8})

    results = solver.solve(m, tee=True)

    pyo.assert_optimal_termination(results)

    return m, results


if __name__ == "__main__":
    # This method builds and runs a steady state activated sludge
    # flowsheet.
    m, results = build_flowsheet()
    stream_table = create_stream_table_dataframe(
        {
            "AD inlet": m.fs.AD.inlet,
            "AD liquid outlet": m.fs.AD.liquid_outlet,
            "Translator outlet": m.fs.translator_adm1_asm2d.outlet,
            "ElectroNP outlet": m.fs.electroNP.treated,
        },
        time_point=0,
    )
    print(stream_table_dataframe_to_string(stream_table))
