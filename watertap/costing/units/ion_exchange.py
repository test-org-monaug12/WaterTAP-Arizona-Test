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

import pyomo.environ as pyo
from idaes.core.util.exceptions import ConfigurationError
from ..util import (
    register_costing_parameter_block,
    make_capital_cost_var,
    make_fixed_operating_cost_var,
)


def build_ion_exhange_cost_param_block(blk):
    blk.anion_exchange_resin_cost = pyo.Var(
        initialize=205,
        units=pyo.units.USD_2020 / pyo.units.ft**3,
        doc="Anion exchange resin cost per cubic ft. Assumes strong base polystyrenic gel-type Type II. From EPA-WBS cost model.",
    )
    blk.cation_exchange_resin_cost = pyo.Var(
        initialize=153,
        units=pyo.units.USD_2020 / pyo.units.ft**3,
        doc="Cation exchange resin cost per cubic ft. Assumes strong acid polystyrenic gel-type. From EPA-WBS cost model.",
    )
    # Ion exchange pressure vessels costed with 3rd order polynomial:
    #   pv_cost = A * col_vol^3 + B * col_vol^2 + C * col_vol + intercept

    blk.vessel_intercept = pyo.Var(
        initialize=10010.86,
        units=pyo.units.USD_2020,
        doc="Ion exchange pressure vessel cost equation - intercept, Carbon steel w/ plastic internals",
    )
    blk.vessel_A_coeff = pyo.Var(
        initialize=6e-9,
        units=pyo.units.USD_2020 / pyo.units.gal**3,
        doc="Ion exchange pressure vessel cost equation - A coeff., Carbon steel w/ plastic internals",
    )
    blk.vessel_B_coeff = pyo.Var(
        initialize=-2.284e-4,
        units=pyo.units.USD_2020 / pyo.units.gal**2,
        doc="Ion exchange pressure vessel cost equation - B coeff., Carbon steel w/ plastic internals",
    )
    blk.vessel_C_coeff = pyo.Var(
        initialize=8.3472,
        units=pyo.units.USD_2020 / pyo.units.gal,
        doc="Ion exchange pressure vessel cost equation - C coeff., Carbon steel w/ plastic internals",
    )
    # Ion exchange pressure vessels costed with 3rd order polynomial:
    #   pv_cost = A * col_vol^3 + B * col_vol^2 + C * col_vol + intercept

    blk.backwash_tank_A_coeff = pyo.Var(
        initialize=1e-9,
        units=pyo.units.USD_2020 / pyo.units.gal**3,
        doc="Ion exchange backwash tank cost equation - A coeff., Fiberglass tank",
    )
    blk.backwash_tank_B_coeff = pyo.Var(
        initialize=-5.8587e-05,
        units=pyo.units.USD_2020 / pyo.units.gal**2,
        doc="Ion exchange backwash tank cost equation - B coeff., Fiberglass tank",
    )
    blk.backwash_tank_C_coeff = pyo.Var(
        initialize=2.2911,
        units=pyo.units.USD_2020 / pyo.units.gal,
        doc="Ion exchange backwash tank cost equation - C coeff., Fiberglass tank",
    )
    blk.backwash_tank_intercept = pyo.Var(
        initialize=4717.255,
        units=pyo.units.dimensionless,
        doc="Ion exchange backwash tank cost equation - exponent, Fiberglass tank",
    )
    # Ion exchange regeneration solution tank costed with 2nd order polynomial:
    #   regen_tank_cost = A * tank_vol^2 + B * tank_vol + intercept

    blk.regen_tank_intercept = pyo.Var(
        initialize=4408.327,
        units=pyo.units.USD_2020 / pyo.units.gal,
        doc="Ion exchange regen tank cost equation - C coeff. Stainless steel",
    )
    blk.regen_tank_A_coeff = pyo.Var(
        initialize=-3.258e-5,
        units=pyo.units.USD_2020 / pyo.units.gal**2,
        doc="Ion exchange regen tank cost equation - A coeff. Stainless steel",
    )
    blk.regen_tank_B_coeff = pyo.Var(
        initialize=3.846,
        units=pyo.units.USD_2020 / pyo.units.gal,
        doc="Ion exchange regen tank cost equation - B coeff. Stainless steel",
    )
    blk.annual_resin_replacement_factor = pyo.Var(
        initialize=0.05,
        units=pyo.units.year**-1,
        doc="Fraction of ion excange resin replaced per year, 4-5% of bed volume - EPA",
    )
    blk.hazardous_min_cost = pyo.Var(
        initialize=3240,
        units=pyo.units.USD_2020,
        doc="Min cost per hazardous waste shipment - EPA",
    )
    blk.hazardous_resin_disposal = pyo.Var(
        initialize=347.10,
        units=pyo.units.USD_2020 * pyo.units.ton**-1,
        doc="Hazardous resin disposal cost - EPA",
    )
    blk.hazardous_regen_disposal = pyo.Var(
        initialize=3.64,
        units=pyo.units.USD_2020 * pyo.units.gal**-1,
        doc="Hazardous liquid disposal cost - EPA",
    )


@register_costing_parameter_block(
    build_rule=build_ion_exhange_cost_param_block,
    parameter_block_name="ion_exchange",
)
def cost_ion_exchange(blk):
    """
    Volume-based capital cost for Ion Exchange
    """
    make_capital_cost_var(blk)
    make_fixed_operating_cost_var(blk)
    # Conversions to use units from cost equations in reference
    col_vol_gal = pyo.units.convert(blk.unit_model.col_vol_per, to_units=pyo.units.gal)
    bed_vol_ft3 = pyo.units.convert(blk.unit_model.bed_vol, to_units=pyo.units.ft**3)
    bed_mass_ton = pyo.units.convert(
        blk.unit_model.bed_vol * blk.unit_model.resin_bulk_dens,
        to_units=pyo.units.ton,
    )
    bw_tank_vol = pyo.units.convert(
        (
            blk.unit_model.bw_flow * blk.unit_model.t_bw
            + blk.unit_model.rinse_flow * blk.unit_model.t_rinse
        ),
        to_units=pyo.units.gal,
    )
    regen_tank_vol = pyo.units.convert(
        (
            blk.unit_model.properties_regen[0].flow_vol_phase["Liq"]
            * blk.unit_model.t_regen
        ),
        to_units=pyo.units.gal,
    )
    ix_type = blk.unit_model.ion_exchange_type
    TIC = 1.65
    blk.capital_cost_vessel = pyo.Var(
        initialize=1e5,
        domain=pyo.NonNegativeReals,
        units=blk.costing_package.base_currency,
        doc="Capital cost for one vessel",
    )
    blk.capital_cost_resin = pyo.Var(
        initialize=1e5,
        domain=pyo.NonNegativeReals,
        units=blk.costing_package.base_currency,
        doc="Capital cost for resin for one vessel",
    )
    blk.capital_cost_regen_tank = pyo.Var(
        initialize=1e5,
        domain=pyo.NonNegativeReals,
        units=blk.costing_package.base_currency,
        doc="Capital cost for regeneration solution tank",
    )
    blk.capital_cost_backwash_tank = pyo.Var(
        initialize=1e5,
        domain=pyo.NonNegativeReals,
        units=blk.costing_package.base_currency,
        doc="Capital cost for backwash + rinse solution tank",
    )
    blk.operating_cost_hazardous = pyo.Var(
        initialize=1e5,
        domain=pyo.NonNegativeReals,
        units=blk.costing_package.base_currency,
        doc="Operating cost for hazardous waste disposal",
    )

    ion_exchange_params = blk.costing_package.ion_exchange

    # TODO: add way to have other regen chemicals
    if ix_type == "cation":
        resin_cost = ion_exchange_params.cation_exchange_resin_cost

    elif ix_type == "anion":
        resin_cost = ion_exchange_params.anion_exchange_resin_cost

    elif ix_type == "mixed":
        raise ConfigurationError(
            "IonExchangeOD model for IonExchangeType.mixed has not been implemented yet."
        )

    blk.capital_cost_vessel_constraint = pyo.Constraint(
        expr=blk.capital_cost_vessel
        == ion_exchange_params.vessel_intercept
        + ion_exchange_params.vessel_A_coeff * col_vol_gal**3
        + ion_exchange_params.vessel_B_coeff * col_vol_gal**2
        + ion_exchange_params.vessel_C_coeff * col_vol_gal
    )
    blk.capital_cost_resin_constraint = pyo.Constraint(
        expr=blk.capital_cost_resin == resin_cost * bed_vol_ft3
    )
    blk.capital_cost_backwash_tank_constraint = pyo.Constraint(
        expr=blk.capital_cost_backwash_tank
        == ion_exchange_params.backwash_tank_intercept
        + ion_exchange_params.backwash_tank_A_coeff * bw_tank_vol**3
        + ion_exchange_params.backwash_tank_B_coeff * bw_tank_vol**2
        + ion_exchange_params.backwash_tank_C_coeff * bw_tank_vol
    )
    blk.capital_cost_regen_tank_constraint = pyo.Constraint(
        expr=blk.capital_cost_regen_tank
        == ion_exchange_params.regen_tank_intercept
        + ion_exchange_params.regen_tank_A_coeff * regen_tank_vol**2
        + ion_exchange_params.regen_tank_B_coeff * regen_tank_vol
    )
    blk.capital_cost_constraint = pyo.Constraint(
        expr=blk.capital_cost
        == (
            (blk.capital_cost_vessel + blk.capital_cost_resin)
            * (blk.unit_model.number_columns + blk.unit_model.number_columns_redund)
            + blk.capital_cost_backwash_tank
            + blk.capital_cost_regen_tank
        )
        * TIC
    )
    if blk.unit_model.config.hazardous_waste:
        blk.operating_cost_hazardous_constraint = pyo.Constraint(
            expr=blk.operating_cost_hazardous
            == (
                bw_tank_vol * ion_exchange_params.hazardous_regen_disposal
                + bed_mass_ton * ion_exchange_params.hazardous_resin_disposal
            )
            * ion_exchange_params.annual_resin_replacement_factor
            + ion_exchange_params.hazardous_min_cost
        )
    else:
        blk.operating_cost_hazardous.fix(0)
    blk.fixed_operating_cost_constraint = pyo.Constraint(
        expr=blk.fixed_operating_cost
        == (
            (
                bed_vol_ft3
                * ion_exchange_params.annual_resin_replacement_factor
                * resin_cost
            )
            + blk.operating_cost_hazardous
        )
    )

    regen_soln_flow = (
        (
            blk.unit_model.regen_dose
            * blk.unit_model.bed_vol
            * (blk.unit_model.number_columns + blk.unit_model.number_columns_redund)
        )
        / (blk.unit_model.t_cycle)
    ) / blk.unit_model.regen_recycle

    electricity_flow = (
        blk.unit_model.main_pump_power
        + blk.unit_model.regen_pump_power
        + blk.unit_model.bw_pump_power
        + blk.unit_model.rinse_pump_power
    )

    blk.costing_package.cost_flow(electricity_flow, "electricity")
    blk.costing_package.cost_flow(regen_soln_flow, blk.unit_model.regen_chem)
