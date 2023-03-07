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
"""
Modified ADM1 reaction package.

Reference:

X. Flores-Alsina, K. Solon, C.K. Mbamba, S. Tait, K.V. Gernaey, U. Jeppsson, D.J. Batstone,
Modelling phosphorus (P), sulfur (S) and iron (Fe) interactions fordynamic simulations of anaerobic digestion processes,
Water Research. 95 (2016) 370-382. https://www.sciencedirect.com/science/article/pii/S0043135416301397

"""

# Import Pyomo libraries
import pyomo.environ as pyo

# Import IDAES cores
from idaes.core import (
    declare_process_block_class,
    MaterialFlowBasis,
    ReactionParameterBlock,
    ReactionBlockDataBase,
    ReactionBlockBase,
)
from idaes.core.util.constants import Constants
from idaes.core.util.misc import add_object_reference
from idaes.core.util.exceptions import BurntToast
import idaes.logger as idaeslog
import idaes.core.util.scaling as iscale

# Some more information about this module
__author__ = "Chenyu Wang, Marcus Holly"

# Set up logger
_log = idaeslog.getLogger(__name__)


@declare_process_block_class("ModifiedADM1ReactionParameterBlock")
class ModifiedADM1ReactionParameterData(ReactionParameterBlock):
    """
    Property Parameter Block Class
    """

    def build(self):
        """
        Callable method for Block construction.
        """
        super().build()

        self._reaction_block_class = ModifiedADM1ReactionBlock

        # Reaction Index
        # Reaction names based on standard numbering in ADM1
        # R1:  Hydrolysis of carbohydrates
        # R2:  Hydrolysis of proteins
        # R3:  Hydrolysis of lipids
        # R4:  Uptake of sugars
        # R5:  Uptake of amino acids
        # R6:  Uptake of long chain fatty acids (LCFAs)
        # R7:  Uptake of valerate
        # R8:  Uptake of butyrate
        # R9: Uptake of propionate
        # R10: Uptake of acetate
        # R11: Uptake of hydrogen
        # R12: Decay of X_su
        # R13: Decay of X_aa
        # R14: Decay of X_fa
        # R15: Decay of X_c4
        # R16: Decay of X_pro
        # R17: Decay of X_ac
        # R18: Decay of X_h2

        self.rate_reaction_idx = pyo.Set(
            initialize=[
                "R1",
                "R2",
                "R3",
                "R4",
                "R5",
                "R6",
                "R7",
                "R8",
                "R9",
                "R10",
                "R11",
                "R12",
                "R13",
                "R14",
                "R15",
                "R16",
                "R17",
                "R18",
            ]
        )

        # Carbon content
        Ci_dict = {
            "S_su": 0.03125000,
            "S_aa": 0.03074155,
            "S_fa": 0.02140411,
            "S_va": 0.02403846,
            "S_bu": 0.0250000,
            "S_pro": 0.02678571,
            "S_ac": 0.031250000,
            "S_ch4": 0.01562500,
            "S_I": 0.03014820,
            "X_ch": 0.03125000,
            "X_pr": 0.03074155,
            "X_li": 0.02192559,
            "X_su": 0.03050979,
            "X_aa": 0.03050979,
            "X_fa": 0.03050979,
            "X_c4": 0.03050979,
            "X_pro": 0.03050979,
            "X_ac": 0.03050979,
            "X_h2": 0.03050979,
            "X_I": 00.03050979,
            "X_PHA": 0.02500000,
            "X_PAO": 0.03050979,
        }

        self.Ci = pyo.Var(
            Ci_dict.keys(),
            initialize=Ci_dict,
            units=pyo.units.kmol / pyo.units.kg,
            domain=pyo.PositiveReals,
            doc="Carbon content of component [kmole C/kg COD]",
        )

        # Nitrogen content
        Ni_dict = {
            "S_aa": 0.0079034,
            "S_I": 0.0042876,
            "X_pr": 0.0079034,
            "X_su": 0.0061532,
            "X_aa": 0.0061532,
            "X_fa": 0.0061532,
            "X_c4": 0.0061532,
            "X_pro": 0.0061532,
            "X_ac": 0.0061532,
            "X_h2": 0.0061532,
            "X_I": 0.0042876,
            "X_PAO": 0.0061532,
        }

        self.Ni = pyo.Var(
            Ni_dict.keys(),
            initialize=Ni_dict,
            units=pyo.units.kmol / pyo.units.kg,
            domain=pyo.PositiveReals,
            doc="Nitrogen content of component [kmole N/kg COD]",
        )

        # Phosphorus content
        Pi_dict = {
            "S_I": 0.0002093,
            "X_li": 0.0003441,
            "X_su": 0.0006947,
            "X_aa": 0.0006947,
            "X_fa": 0.0006947,
            "X_c4": 0.0006947,
            "X_pro": 0.0006947,
            "X_ac": 0.0006947,
            "X_h2": 0.0006947,
            "X_I": 0.0002093,
            "X_PAO": 0.0006947,
        }

        self.Pi = pyo.Var(
            Pi_dict.keys(),
            initialize=Pi_dict,
            units=pyo.units.kmol / pyo.units.kg,
            domain=pyo.PositiveReals,
            doc="Phosphorus content of component [kmole P/kg COD]",
        )

        mw_n = 14 * pyo.units.kg / pyo.units.kmol
        mw_c = 12 * pyo.units.kg / pyo.units.kmol
        mw_p = 31 * pyo.units.kg / pyo.units.kmol

        # TODO: Inherit these parameters from ADM1 such that there is less repeated code?

        # Stoichiometric Parameters (Table 6.1 in Batstone et al., 2002)
        self.f_sI_xc = pyo.Var(
            initialize=0.1,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Soluble inerts from composites",
        )
        self.f_xI_xc = pyo.Var(
            initialize=0.20,  # replacing 0.25 with 0.2 in accordance with Rosen & Jeppsson, 2006
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Particulate inerts from composites",
        )
        self.f_ch_xc = pyo.Var(
            initialize=0.2,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Carbohydrates from composites",
        )
        self.f_pr_xc = pyo.Var(
            initialize=0.2,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Proteins from composites",
        )
        self.f_li_xc = pyo.Var(
            initialize=0.30,  # replacing 0.25 with 0.3 in accordance with Rosen & Jeppsson, 2006
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Lipids from composites",
        )
        self.N_xc = pyo.Var(
            initialize=0.0376
            / 14,  # change from 0.002 to 0.0376/14 based on Rosen & Jeppsson, 2006
            units=pyo.units.kmol * pyo.units.kg**-1,
            domain=pyo.PositiveReals,
            doc="Nitrogen content of composites [kmole N/kg COD]",
        )
        self.N_I = pyo.Var(
            initialize=0.06
            / 14,  # change from 0.002 to 0.06/14 based on Rosen & Jeppsson, 2006
            units=pyo.units.kmol * pyo.units.kg**-1,
            domain=pyo.PositiveReals,
            doc="Nitrogen content of inerts [kmole N/kg COD]",
        )
        self.N_aa = pyo.Var(
            initialize=0.007,
            units=pyo.units.kmol * pyo.units.kg**-1,
            domain=pyo.PositiveReals,
            doc="Nitrogen in amino acids and proteins [kmole N/kg COD]",
        )
        self.N_bac = pyo.Var(
            initialize=0.08 / 14,
            units=pyo.units.kmol * pyo.units.kg**-1,
            # units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Nitrogen content in bacteria [kmole N/kg COD]",
        )
        self.f_fa_li = pyo.Var(
            initialize=0.95,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Fatty acids from lipids",
        )
        self.f_h2_su = pyo.Var(
            initialize=0.1906,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Hydrogen from sugars",
        )
        self.f_bu_su = pyo.Var(
            initialize=0.1328,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Butyrate from sugars",
        )
        self.f_pro_su = pyo.Var(
            initialize=0.2691,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Propionate from sugars",
        )
        self.f_ac_su = pyo.Var(
            initialize=0.4076,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Acetate from sugars",
        )
        self.f_h2_aa = pyo.Var(
            initialize=0.06,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Hydrogen from amino acids",
        )

        self.f_va_aa = pyo.Var(
            initialize=0.23,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Valerate from amino acids",
        )
        self.f_bu_aa = pyo.Var(
            initialize=0.26,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Butyrate from amino acids",
        )
        self.f_pro_aa = pyo.Var(
            initialize=0.05,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Propionate from amino acids",
        )
        self.f_ac_aa = pyo.Var(
            initialize=0.40,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Acetate from amino acids",
        )
        self.Y_su = pyo.Var(
            initialize=0.10,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Yield of biomass on sugar substrate [kg COD X/ kg COD S]",
        )
        self.Y_aa = pyo.Var(
            initialize=0.08,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Yield of biomass on amino acid substrate [kg COD X/ kg COD S]",
        )
        self.Y_fa = pyo.Var(
            initialize=0.06,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Yield of biomass on fatty acid substrate [kg COD X/ kg COD S]",
        )
        self.Y_c4 = pyo.Var(
            initialize=0.06,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Yield of biomass on valerate and butyrate substrate [kg COD X/ kg COD S]",
        )
        self.Y_pro = pyo.Var(
            initialize=0.04,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Yield of biomass on propionate substrate [kg COD X/ kg COD S]",
        )
        self.Y_ac = pyo.Var(
            initialize=0.05,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Yield of biomass on acetate substrate [kg COD X/ kg COD S]",
        )
        self.Y_h2 = pyo.Var(
            initialize=0.06,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Yield of hydrogen per biomass [kg COD S/ kg COD X]",
        )
        # Biochemical Parameters
        self.k_dis = pyo.Var(
            initialize=0.5,
            units=pyo.units.day**-1,
            domain=pyo.PositiveReals,
            doc="First-order kinetic parameter for disintegration",
        )
        self.k_hyd_ch = pyo.Var(
            initialize=10,
            units=pyo.units.day**-1,
            domain=pyo.PositiveReals,
            doc="First-order kinetic parameter for hydrolysis of carbohydrates",
        )
        self.k_hyd_pr = pyo.Var(
            initialize=10,
            units=pyo.units.day**-1,
            domain=pyo.PositiveReals,
            doc="First-order kinetic parameter for hydrolysis of proteins",
        )
        self.k_hyd_li = pyo.Var(
            initialize=10,
            units=pyo.units.day**-1,
            domain=pyo.PositiveReals,
            doc="First-order kinetic parameter for hydrolysis of lipids",
        )
        self.K_S_IN = pyo.Var(
            initialize=1e-4,
            units=pyo.units.kmol * pyo.units.m**-3,
            domain=pyo.PositiveReals,
            doc="Inhibition parameter for inorganic nitrogen",
        )
        self.k_m_su = pyo.Var(
            initialize=30,
            units=pyo.units.day**-1,
            domain=pyo.PositiveReals,
            doc="Monod maximum specific uptake rate of sugars",
        )
        self.K_S_su = pyo.Var(
            initialize=0.5,
            units=pyo.units.kg * pyo.units.m**-3,
            domain=pyo.PositiveReals,
            doc="Half saturation value for uptake of sugars",
        )
        self.pH_UL_aa = pyo.Var(
            initialize=5.5,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Upper limit of pH for uptake rate of amino acids",
        )
        self.pH_LL_aa = pyo.Var(
            initialize=4,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Lower limit of pH for uptake rate of amino acids",
        )
        self.k_m_aa = pyo.Var(
            initialize=50,
            units=pyo.units.day**-1,
            domain=pyo.PositiveReals,
            doc="Monod maximum specific uptake rate of amino acids",
        )

        self.K_S_aa = pyo.Var(
            initialize=0.3,
            units=pyo.units.kg * pyo.units.m**-3,
            domain=pyo.PositiveReals,
            doc="Half saturation value for uptake of amino acids",
        )
        self.k_m_fa = pyo.Var(
            initialize=6,
            units=pyo.units.day**-1,
            domain=pyo.PositiveReals,
            doc="Monod maximum specific uptake rate of fatty acids",
        )
        self.K_S_fa = pyo.Var(
            initialize=0.4,
            units=pyo.units.kg * pyo.units.m**-3,
            domain=pyo.PositiveReals,
            doc="Half saturation value for uptake of fatty acids",
        )
        self.K_I_h2_fa = pyo.Var(
            initialize=5e-6,
            units=pyo.units.kg * pyo.units.m**-3,
            domain=pyo.PositiveReals,
            doc="Inhibition parameter for hydrogen during uptake of fatty acids",
        )
        self.k_m_c4 = pyo.Var(
            initialize=20,
            units=pyo.units.day**-1,
            domain=pyo.PositiveReals,
            doc="Monod maximum specific uptake rate of valerate and butyrate",
        )
        self.K_S_c4 = pyo.Var(
            initialize=0.2,
            units=pyo.units.kg * pyo.units.m**-3,
            domain=pyo.PositiveReals,
            doc="Half saturation value for uptake of valerate and butyrate",
        )
        self.K_I_h2_c4 = pyo.Var(
            initialize=1e-5,
            units=pyo.units.kg * pyo.units.m**-3,
            domain=pyo.PositiveReals,
            doc="Inhibition parameter for hydrogen during uptake of valerate and butyrate",
        )
        self.k_m_pro = pyo.Var(
            initialize=13,
            units=pyo.units.day**-1,
            domain=pyo.PositiveReals,
            doc="Monod maximum specific uptake rate of propionate",
        )
        self.K_S_pro = pyo.Var(
            initialize=0.1,
            units=pyo.units.kg * pyo.units.m**-3,
            domain=pyo.PositiveReals,
            doc="Half saturation value for uptake of propionate",
        )
        self.K_I_h2_pro = pyo.Var(
            initialize=3.5e-6,
            units=pyo.units.kg * pyo.units.m**-3,
            domain=pyo.PositiveReals,
            doc="Inhibition parameter for hydrogen during uptake of propionate",
        )
        self.k_m_ac = pyo.Var(
            initialize=8,
            units=pyo.units.day**-1,
            domain=pyo.PositiveReals,
            doc="Monod maximum specific uptake rate of acetate",
        )
        self.K_S_ac = pyo.Var(
            initialize=0.15,
            units=pyo.units.kg * pyo.units.m**-3,
            domain=pyo.PositiveReals,
            doc="Half saturation value for uptake of acetate",
        )
        self.K_I_nh3 = pyo.Var(
            initialize=0.0018,
            units=pyo.units.kmol * pyo.units.m**-3,
            domain=pyo.PositiveReals,
            doc="Inhibition parameter for ammonia during uptake of acetate",
        )
        self.pH_UL_ac = pyo.Var(
            initialize=7,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Upper limit of pH for uptake rate of acetate",
        )
        self.pH_LL_ac = pyo.Var(
            initialize=6,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Lower limit of pH for uptake rate of acetate",
        )
        self.k_m_h2 = pyo.Var(
            initialize=35,
            units=pyo.units.day**-1,
            domain=pyo.PositiveReals,
            doc="Monod maximum specific uptake rate of hydrogen",
        )
        self.K_S_h2 = pyo.Var(
            initialize=7e-6,
            units=pyo.units.kg * pyo.units.m**-3,
            domain=pyo.PositiveReals,
            doc="Half saturation value for uptake of hydrogen",
        )
        self.pH_UL_h2 = pyo.Var(
            initialize=6,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Upper limit of pH for uptake rate of hydrogen",
        )
        self.pH_LL_h2 = pyo.Var(
            initialize=5,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Lower limit of pH for uptake rate of hydrogen",
        )
        self.k_dec_X_su = pyo.Var(
            initialize=0.02,
            units=pyo.units.day**-1,
            domain=pyo.PositiveReals,
            doc="First-order decay rate for X_su",
        )
        self.k_dec_X_aa = pyo.Var(
            initialize=0.02,
            units=pyo.units.day**-1,
            domain=pyo.PositiveReals,
            doc="First-order decay rate for X_aa",
        )
        self.k_dec_X_fa = pyo.Var(
            initialize=0.02,
            units=pyo.units.day**-1,
            domain=pyo.PositiveReals,
            doc="First-order decay rate for X_fa",
        )
        self.k_dec_X_c4 = pyo.Var(
            initialize=0.02,
            units=pyo.units.day**-1,
            domain=pyo.PositiveReals,
            doc="First-order decay rate for X_c4",
        )
        self.k_dec_X_pro = pyo.Var(
            initialize=0.02,
            units=pyo.units.day**-1,
            domain=pyo.PositiveReals,
            doc="First-order decay rate for X_pro",
        )
        self.k_dec_X_ac = pyo.Var(
            initialize=0.02,
            units=pyo.units.day**-1,
            domain=pyo.PositiveReals,
            doc="First-order decay rate for X_ac",
        )
        self.k_dec_X_h2 = pyo.Var(
            initialize=0.02,
            units=pyo.units.day**-1,
            domain=pyo.PositiveReals,
            doc="First-order decay rate for X_h2",
        )
        self.K_a_va = pyo.Var(
            initialize=1.38e-5,
            units=pyo.units.kmol / pyo.units.m**3,
            domain=pyo.PositiveReals,
            doc="Valerate acid-base equilibrium constant",
        )
        self.K_a_bu = pyo.Var(
            initialize=1.5e-5,
            units=pyo.units.kmol / pyo.units.m**3,
            domain=pyo.PositiveReals,
            doc="Butyrate acid-base equilibrium constant",
        )
        self.K_a_pro = pyo.Var(
            initialize=1.32e-5,
            units=pyo.units.kmol / pyo.units.m**3,
            domain=pyo.PositiveReals,
            doc="Propionate acid-base equilibrium constant",
        )
        self.K_a_ac = pyo.Var(
            initialize=1.74e-5,
            units=pyo.units.kmol / pyo.units.m**3,
            domain=pyo.PositiveReals,
            doc="Acetate acid-base equilibrium constant",
        )
        self.f_xi_xb = pyo.Var(
            initialize=0.1,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Fraction of inert particulate organics from biomass",
        )
        self.f_ch_xb = pyo.Var(
            initialize=0.275,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Fraction of carbohydrates from biomass",
        )
        self.f_li_xb = pyo.Var(
            initialize=0.350,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Fraction of lipids from biomass",
        )
        self.f_pr_xb = pyo.Var(
            initialize=0.275,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Fraction of proteins from biomass",
        )
        self.f_sl_xb = pyo.Var(
            initialize=0,  # Check this value
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Fraction of soluble inerts from biomass",
        )
        self.f_xl_xb = pyo.Var(
            initialize=0.1,
            units=pyo.units.dimensionless,
            domain=pyo.PositiveReals,
            doc="Fraction of particulate inerts from biomass",
        )
        self.K_I_h2s_ac = pyo.Var(
            initialize=460e-3,
            units=pyo.units.kg / pyo.units.m**3,
            domain=pyo.PositiveReals,
            doc="50% inhibitory concentration of H2S on acetogens",
        )
        self.K_I_h2s_c4 = pyo.Var(
            initialize=481e-3,
            units=pyo.units.kg / pyo.units.m**3,
            domain=pyo.PositiveReals,
            doc="50% inhibitory concentration of H2S on c4 degraders",
        )
        self.K_I_h2s_h2 = pyo.Var(
            initialize=400e-3,
            units=pyo.units.kg / pyo.units.m**3,
            domain=pyo.PositiveReals,
            doc="50% inhibitory concentration of H2S on hydrogenotrophic methanogens",
        )
        self.K_I_h2s_pro = pyo.Var(
            initialize=481e-3,
            units=pyo.units.kg / pyo.units.m**3,
            domain=pyo.PositiveReals,
            doc="50% inhibitory concentration of propionate degraders",
        )
        self.K_S_IP = pyo.Var(
            initialize=2e-5,
            units=pyo.units.kmol / pyo.units.m**3,
            domain=pyo.PositiveReals,
            doc="P limitation for inorganic phosphorus",
        )
        self.temperature_ref = pyo.Param(
            within=pyo.PositiveReals,
            mutable=True,
            default=298.15,
            doc="Reference temperature",
            units=pyo.units.K,
        )

        # Reaction Stoichiometry
        # This is the stoichiometric part of the Peterson matrix in dict form.
        # See Table 1.1 in Flores-Alsina et al., 2016.

        # Exclude non-zero stoichiometric coefficients for S_IC initially since they depend on other stoichiometric coefficients.
        self.rate_reaction_stoichiometry = {
            # R1: Hydrolysis of carbohydrates
            ("R1", "Liq", "H2O"): 0,
            ("R1", "Liq", "S_su"): 1,
            ("R1", "Liq", "S_aa"): 0,
            ("R1", "Liq", "S_fa"): 0,
            ("R1", "Liq", "S_va"): 0,
            ("R1", "Liq", "S_bu"): 0,
            ("R1", "Liq", "S_pro"): 0,
            ("R1", "Liq", "S_ac"): 0,
            ("R1", "Liq", "S_h2"): 0,
            ("R1", "Liq", "S_ch4"): 0,
            ("R1", "Liq", "S_IC"): -(self.Ci["S_su"] - self.Ci["X_ch"]) * mw_c,
            ("R1", "Liq", "S_IN"): 0,
            ("R1", "Liq", "S_IP"): 0,
            ("R1", "Liq", "S_I"): 0,
            ("R1", "Liq", "X_ch"): -1,
            ("R1", "Liq", "X_pr"): 0,
            ("R1", "Liq", "X_li"): 0,
            ("R1", "Liq", "X_su"): 0,
            ("R1", "Liq", "X_aa"): 0,
            ("R1", "Liq", "X_fa"): 0,
            ("R1", "Liq", "X_c4"): 0,
            ("R1", "Liq", "X_pro"): 0,
            ("R1", "Liq", "X_ac"): 0,
            ("R1", "Liq", "X_h2"): 0,
            ("R1", "Liq", "X_I"): 0,
            # R2:  Hydrolysis of proteins
            ("R2", "Liq", "H2O"): 0,
            ("R2", "Liq", "S_su"): 0,
            ("R2", "Liq", "S_aa"): 1,
            ("R2", "Liq", "S_fa"): 0,
            ("R2", "Liq", "S_va"): 0,
            ("R2", "Liq", "S_bu"): 0,
            ("R2", "Liq", "S_pro"): 0,
            ("R2", "Liq", "S_ac"): 0,
            ("R2", "Liq", "S_h2"): 0,
            ("R2", "Liq", "S_ch4"): 0,
            ("R2", "Liq", "S_IC"): -(self.Ci["S_aa"] - self.Ci["X_pr"]) * mw_c,
            ("R2", "Liq", "S_IN"): -(self.Ni["S_aa"] - self.Ni["X_pr"]) * mw_n,
            ("R2", "Liq", "S_IP"): 0,
            ("R2", "Liq", "S_I"): 0,
            ("R2", "Liq", "X_ch"): 0,
            ("R2", "Liq", "X_pr"): -1,
            ("R2", "Liq", "X_li"): 0,
            ("R2", "Liq", "X_su"): 0,
            ("R2", "Liq", "X_aa"): 0,
            ("R2", "Liq", "X_fa"): 0,
            ("R2", "Liq", "X_c4"): 0,
            ("R2", "Liq", "X_pro"): 0,
            ("R2", "Liq", "X_ac"): 0,
            ("R2", "Liq", "X_h2"): 0,
            ("R2", "Liq", "X_I"): 0,
            # R3:  Hydrolysis of lipids
            ("R3", "Liq", "H2O"): 0,
            ("R3", "Liq", "S_su"): 1 - self.f_fa_li,
            ("R3", "Liq", "S_aa"): 0,
            ("R3", "Liq", "S_fa"): self.f_fa_li,
            ("R3", "Liq", "S_va"): 0,
            ("R3", "Liq", "S_bu"): 0,
            ("R3", "Liq", "S_pro"): 0,
            ("R3", "Liq", "S_ac"): 0,
            ("R3", "Liq", "S_h2"): 0,
            ("R3", "Liq", "S_ch4"): 0,
            ("R3", "Liq", "S_IC"): (
                self.Ci["X_li"]
                - (1 - self.f_fa_li) * self.Ci["S_su"]
                - self.f_fa_li * self.Ci["S_fa"]
            )
            * mw_c,
            ("R3", "Liq", "S_IN"): 0,
            ("R3", "Liq", "S_IP"): self.Pi["X_li"] * mw_p,
            ("R3", "Liq", "S_I"): 0,
            ("R3", "Liq", "X_ch"): 0,
            ("R3", "Liq", "X_pr"): 0,
            ("R3", "Liq", "X_li"): -1,
            ("R3", "Liq", "X_su"): 0,
            ("R3", "Liq", "X_aa"): 0,
            ("R3", "Liq", "X_fa"): 0,
            ("R3", "Liq", "X_c4"): 0,
            ("R3", "Liq", "X_pro"): 0,
            ("R3", "Liq", "X_ac"): 0,
            ("R3", "Liq", "X_h2"): 0,
            ("R3", "Liq", "X_I"): 0,
            # R4:  Uptake of sugars
            ("R4", "Liq", "H2O"): 0,
            ("R4", "Liq", "S_su"): -1,
            ("R4", "Liq", "S_aa"): 0,
            ("R4", "Liq", "S_fa"): 0,
            ("R4", "Liq", "S_va"): 0,
            ("R4", "Liq", "S_bu"): (1 - self.Y_su) * self.f_bu_su,
            ("R4", "Liq", "S_pro"): (1 - self.Y_su) * self.f_pro_su,
            ("R4", "Liq", "S_ac"): (1 - self.Y_su) * self.f_ac_su,
            ("R4", "Liq", "S_h2"): (1 - self.Y_su) * self.f_h2_su,
            ("R4", "Liq", "S_ch4"): 0,
            ("R4", "Liq", "S_IC"): (
                self.Ci["S_su"]
                - (1 - self.Y_su)
                * (
                    self.f_bu_su * self.Ci["S_bu"]
                    + self.f_pro_su * self.Ci["S_pro"]
                    + self.f_ac_su * self.Ci["S_ac"]
                )
                - self.Y_su * self.Ci["X_su"]
            )
            * mw_c,
            ("R4", "Liq", "S_IN"): (-self.Y_su * self.Ni["X_su"]) * mw_n,
            ("R4", "Liq", "S_IP"): (-self.Y_su * self.Pi["X_su"]) * mw_p,
            ("R4", "Liq", "S_I"): 0,
            ("R4", "Liq", "X_ch"): 0,
            ("R4", "Liq", "X_pr"): 0,
            ("R4", "Liq", "X_li"): 0,
            ("R4", "Liq", "X_su"): self.Y_su,
            ("R4", "Liq", "X_aa"): 0,
            ("R4", "Liq", "X_fa"): 0,
            ("R4", "Liq", "X_c4"): 0,
            ("R4", "Liq", "X_pro"): 0,
            ("R4", "Liq", "X_ac"): 0,
            ("R4", "Liq", "X_h2"): 0,
            ("R4", "Liq", "X_I"): 0,
            # R5:  Uptake of amino acids
            ("R5", "Liq", "H2O"): 0,
            ("R5", "Liq", "S_su"): 0,
            ("R5", "Liq", "S_aa"): -1,
            ("R5", "Liq", "S_fa"): 0,
            ("R5", "Liq", "S_va"): (1 - self.Y_aa) * self.f_va_aa,
            ("R5", "Liq", "S_bu"): (1 - self.Y_aa) * self.f_bu_aa,
            ("R5", "Liq", "S_pro"): (1 - self.Y_aa) * self.f_pro_aa,
            ("R5", "Liq", "S_ac"): (1 - self.Y_aa) * self.f_ac_aa,
            ("R5", "Liq", "S_h2"): (1 - self.Y_aa) * self.f_h2_aa,
            ("R5", "Liq", "S_ch4"): 0,
            ("R5", "Liq", "S_IC"): (
                self.Ci["S_aa"]
                - (1 - self.Y_aa)
                * (
                    self.f_va_aa * self.Ci["S_va"]
                    + self.f_bu_aa * self.Ci["S_bu"]
                    + self.f_pro_aa * self.Ci["S_pro"]
                    + self.f_ac_aa * self.Ci["S_ac"]
                )
                - self.Y_aa * self.Ci["X_aa"]
            )
            * mw_c,
            ("R5", "Liq", "S_IN"): -(-self.Ni["S_aa"] + self.Y_aa * self.Ni["X_aa"])
            * mw_n,
            ("R5", "Liq", "S_IP"): -(self.Y_aa * self.Pi["X_aa"]) * mw_p,
            ("R5", "Liq", "S_I"): 0,
            ("R5", "Liq", "X_ch"): 0,
            ("R5", "Liq", "X_pr"): 0,
            ("R5", "Liq", "X_li"): 0,
            ("R5", "Liq", "X_su"): 0,
            ("R5", "Liq", "X_aa"): self.Y_aa,
            ("R5", "Liq", "X_fa"): 0,
            ("R5", "Liq", "X_c4"): 0,
            ("R5", "Liq", "X_pro"): 0,
            ("R5", "Liq", "X_ac"): 0,
            ("R5", "Liq", "X_h2"): 0,
            ("R5", "Liq", "X_I"): 0,
            # R6:  Uptake of long chain fatty acids (LCFAs)
            ("R6", "Liq", "H2O"): 0,
            ("R6", "Liq", "S_su"): 0,
            ("R6", "Liq", "S_aa"): 0,
            ("R6", "Liq", "S_fa"): -1,
            ("R6", "Liq", "S_va"): 0,
            ("R6", "Liq", "S_bu"): 0,
            ("R6", "Liq", "S_pro"): 0,
            ("R6", "Liq", "S_ac"): (1 - self.Y_fa) * 0.7,
            ("R6", "Liq", "S_h2"): (1 - self.Y_fa) * 0.3,
            ("R6", "Liq", "S_ch4"): 0,
            ("R6", "Liq", "S_IC"): (
                self.Ci["S_fa"]
                - (1 - self.Y_fa) * 0.7 * self.Ci["S_ac"]
                - self.Y_fa * self.Ci["X_fa"]
            )
            * mw_c,
            ("R6", "Liq", "S_IN"): (-self.Y_fa * self.Ni["X_fa"]) * mw_n,
            ("R6", "Liq", "S_IP"): (-self.Y_fa * self.Pi["X_fa"]) * mw_p,
            ("R6", "Liq", "S_I"): 0,
            ("R6", "Liq", "X_ch"): 0,
            ("R6", "Liq", "X_pr"): 0,
            ("R6", "Liq", "X_li"): 0,
            ("R6", "Liq", "X_su"): 0,
            ("R6", "Liq", "X_aa"): 0,
            ("R6", "Liq", "X_fa"): self.Y_fa,
            ("R6", "Liq", "X_c4"): 0,
            ("R6", "Liq", "X_pro"): 0,
            ("R6", "Liq", "X_ac"): 0,
            ("R6", "Liq", "X_h2"): 0,
            ("R6", "Liq", "X_I"): 0,
            # R7:  Uptake of valerate
            ("R7", "Liq", "H2O"): 0,
            ("R7", "Liq", "S_su"): 0,
            ("R7", "Liq", "S_aa"): 0,
            ("R7", "Liq", "S_fa"): 0,
            ("R7", "Liq", "S_va"): -1,
            ("R7", "Liq", "S_bu"): 0,
            ("R7", "Liq", "S_pro"): (1 - self.Y_c4) * 0.54,
            ("R7", "Liq", "S_ac"): (1 - self.Y_c4) * 0.31,
            ("R7", "Liq", "S_h2"): (1 - self.Y_c4) * 0.15,
            ("R7", "Liq", "S_ch4"): 0,
            ("R7", "Liq", "S_IC"): (
                self.Ci["S_va"]
                - (1 - self.Y_c4) * 0.54 * self.Ci["S_pro"]
                - (1 - self.Y_c4) * 0.31 * self.Ci["S_ac"]
                - self.Y_c4 * self.Ci["X_c4"]
            )
            * mw_c,
            ("R7", "Liq", "S_IN"): (-self.Y_c4 * self.Ni["X_c4"]) * mw_n,
            ("R7", "Liq", "S_IP"): (-self.Y_c4 * self.Pi["X_c4"]) * mw_p,
            ("R7", "Liq", "S_I"): 0,
            ("R7", "Liq", "X_ch"): 0,
            ("R7", "Liq", "X_pr"): 0,
            ("R7", "Liq", "X_li"): 0,
            ("R7", "Liq", "X_su"): 0,
            ("R7", "Liq", "X_aa"): 0,
            ("R7", "Liq", "X_fa"): 0,
            ("R7", "Liq", "X_c4"): self.Y_c4,
            ("R7", "Liq", "X_pro"): 0,
            ("R7", "Liq", "X_ac"): 0,
            ("R7", "Liq", "X_h2"): 0,
            ("R7", "Liq", "X_I"): 0,
            # R8:  Uptake of butyrate
            ("R8", "Liq", "H2O"): 0,
            ("R8", "Liq", "S_su"): 0,
            ("R8", "Liq", "S_aa"): 0,
            ("R8", "Liq", "S_fa"): 0,
            ("R8", "Liq", "S_va"): 0,
            ("R8", "Liq", "S_bu"): -1,
            ("R8", "Liq", "S_pro"): 0,
            ("R8", "Liq", "S_ac"): (1 - self.Y_c4) * 0.8,
            ("R8", "Liq", "S_h2"): (1 - self.Y_c4) * 0.2,
            ("R8", "Liq", "S_ch4"): 0,
            ("R8", "Liq", "S_IC"): (
                self.Ci["S_bu"]
                - (1 - self.Y_c4) * 0.8 * self.Ci["S_ac"]
                - self.Y_c4 * self.Ci["X_c4"]
            )
            * mw_c,
            ("R8", "Liq", "S_IN"): (-self.Y_c4 * self.Ni["X_c4"]) * mw_n,
            ("R8", "Liq", "S_IP"): (-self.Y_c4 * self.Pi["X_c4"]) * mw_p,
            ("R8", "Liq", "S_I"): 0,
            ("R8", "Liq", "X_ch"): 0,
            ("R8", "Liq", "X_pr"): 0,
            ("R8", "Liq", "X_li"): 0,
            ("R8", "Liq", "X_su"): 0,
            ("R8", "Liq", "X_aa"): 0,
            ("R8", "Liq", "X_fa"): 0,
            ("R8", "Liq", "X_c4"): self.Y_c4,
            ("R8", "Liq", "X_pro"): 0,
            ("R8", "Liq", "X_ac"): 0,
            ("R8", "Liq", "X_h2"): 0,
            ("R8", "Liq", "X_I"): 0,
            # R9: Uptake of propionate
            ("R9", "Liq", "H2O"): 0,
            ("R9", "Liq", "S_su"): 0,
            ("R9", "Liq", "S_aa"): 0,
            ("R9", "Liq", "S_fa"): 0,
            ("R9", "Liq", "S_va"): 0,
            ("R9", "Liq", "S_bu"): 0,
            ("R9", "Liq", "S_pro"): -1,
            ("R9", "Liq", "S_ac"): (1 - self.Y_pro) * 0.57,
            ("R9", "Liq", "S_h2"): (1 - self.Y_pro) * 0.43,
            ("R9", "Liq", "S_ch4"): 0,
            ("R9", "Liq", "S_IC"): (
                self.Ci["S_pro"]
                - (1 - self.Y_pro) * 0.57 * self.Ci["S_ac"]
                - self.Y_pro * self.Ci["X_pro"]
            )
            * mw_c,
            ("R9", "Liq", "S_IN"): (-self.Y_pro * self.Ni["X_pro"]) * mw_n,
            ("R9", "Liq", "S_IP"): (-self.Y_pro * self.Pi["X_pro"]) * mw_p,
            ("R9", "Liq", "S_I"): 0,
            ("R9", "Liq", "X_ch"): 0,
            ("R9", "Liq", "X_pr"): 0,
            ("R9", "Liq", "X_li"): 0,
            ("R9", "Liq", "X_su"): 0,
            ("R9", "Liq", "X_aa"): 0,
            ("R9", "Liq", "X_fa"): 0,
            ("R9", "Liq", "X_c4"): 0,
            ("R9", "Liq", "X_pro"): self.Y_pro,
            ("R9", "Liq", "X_ac"): 0,
            ("R9", "Liq", "X_h2"): 0,
            ("R9", "Liq", "X_I"): 0,
            # R10: Uptake of acetate
            ("R10", "Liq", "H2O"): 0,
            ("R10", "Liq", "S_su"): 0,
            ("R10", "Liq", "S_aa"): 0,
            ("R10", "Liq", "S_fa"): 0,
            ("R10", "Liq", "S_va"): 0,
            ("R10", "Liq", "S_bu"): 0,
            ("R10", "Liq", "S_pro"): 0,
            ("R10", "Liq", "S_ac"): -1,
            ("R10", "Liq", "S_h2"): 0,
            ("R10", "Liq", "S_ch4"): 1 - self.Y_ac,
            ("R10", "Liq", "S_IC"): (
                self.Ci["S_ac"]
                - (1 - self.Y_ac) * self.Ci["S_ch4"]
                - self.Y_ac * self.Ci["X_ac"]
            )
            * mw_c,
            ("R10", "Liq", "S_IN"): (-self.Y_ac * self.Ni["X_ac"]) * mw_n,
            ("R10", "Liq", "S_IP"): (-self.Y_ac * self.Pi["X_ac"]) * mw_p,
            ("R10", "Liq", "S_I"): 0,
            ("R10", "Liq", "X_ch"): 0,
            ("R10", "Liq", "X_pr"): 0,
            ("R10", "Liq", "X_li"): 0,
            ("R10", "Liq", "X_su"): 0,
            ("R10", "Liq", "X_aa"): 0,
            ("R10", "Liq", "X_fa"): 0,
            ("R10", "Liq", "X_c4"): 0,
            ("R10", "Liq", "X_pro"): 0,
            ("R10", "Liq", "X_ac"): self.Y_ac,
            ("R10", "Liq", "X_h2"): 0,
            ("R10", "Liq", "X_I"): 0,
            # R11: Uptake of hydrogen
            ("R11", "Liq", "H2O"): 0,
            ("R11", "Liq", "S_su"): 0,
            ("R11", "Liq", "S_aa"): 0,
            ("R11", "Liq", "S_fa"): 0,
            ("R11", "Liq", "S_va"): 0,
            ("R11", "Liq", "S_bu"): 0,
            ("R11", "Liq", "S_pro"): 0,
            ("R11", "Liq", "S_ac"): 0,
            ("R11", "Liq", "S_h2"): -1,
            ("R11", "Liq", "S_ch4"): 1 - self.Y_h2,
            ("R11", "Liq", "S_IC"): (
                -(1 - self.Y_h2) * self.Ci["S_ch4"] - self.Y_h2 * self.Ci["X_h2"]
            )
            * mw_c,
            ("R11", "Liq", "S_IN"): (-self.Y_h2 * self.Ni["X_h2"]) * mw_n,
            ("R11", "Liq", "S_IP"): (-self.Y_h2 * self.Pi["X_h2"]) * mw_p,
            ("R11", "Liq", "S_I"): 0,
            ("R11", "Liq", "X_ch"): 0,
            ("R11", "Liq", "X_pr"): 0,
            ("R11", "Liq", "X_li"): 0,
            ("R11", "Liq", "X_su"): 0,
            ("R11", "Liq", "X_aa"): 0,
            ("R11", "Liq", "X_fa"): 0,
            ("R11", "Liq", "X_c4"): 0,
            ("R11", "Liq", "X_pro"): 0,
            ("R11", "Liq", "X_ac"): 0,
            ("R11", "Liq", "X_h2"): self.Y_h2,
            ("R11", "Liq", "X_I"): 0,
            # R12: Decay of X_su
            ("R12", "Liq", "H2O"): 0,
            ("R12", "Liq", "S_su"): 0,
            ("R12", "Liq", "S_aa"): 0,
            ("R12", "Liq", "S_fa"): 0,
            ("R12", "Liq", "S_va"): 0,
            ("R12", "Liq", "S_bu"): 0,
            ("R12", "Liq", "S_pro"): 0,
            ("R12", "Liq", "S_ac"): 0,
            ("R12", "Liq", "S_h2"): 0,
            ("R12", "Liq", "S_ch4"): 0,
            ("R12", "Liq", "S_IC"): (
                self.Ci["X_su"]
                - self.f_ch_xb * self.Ci["X_ch"]
                - self.f_pr_xb * self.Ci["X_pr"]
                - self.f_li_xb * self.Ci["X_li"]
                - self.f_xi_xb * self.Ci["X_I"]
            )
            * mw_c,
            ("R12", "Liq", "S_IN"): (
                self.Ni["X_su"]
                - self.f_pr_xb * self.Ni["X_pr"]
                - self.f_xi_xb * self.Ni["X_I"]
            )
            * mw_n,
            ("R12", "Liq", "S_IP"): (
                self.Pi["X_su"]
                - self.f_li_xb * self.Pi["X_li"]
                - self.f_xi_xb * self.Pi["X_I"]
            )
            * mw_p,
            ("R12", "Liq", "S_I"): 0,
            ("R12", "Liq", "X_ch"): self.f_ch_xb,
            ("R12", "Liq", "X_pr"): self.f_pr_xb,
            ("R12", "Liq", "X_li"): self.f_li_xb,
            ("R12", "Liq", "X_su"): -1,
            ("R12", "Liq", "X_aa"): 0,
            ("R12", "Liq", "X_fa"): 0,
            ("R12", "Liq", "X_c4"): 0,
            ("R12", "Liq", "X_pro"): 0,
            ("R12", "Liq", "X_ac"): 0,
            ("R12", "Liq", "X_h2"): 0,
            ("R12", "Liq", "X_I"): self.f_xi_xb,
            # R13: Decay of X_aa
            ("R13", "Liq", "H2O"): 0,
            ("R13", "Liq", "S_su"): 0,
            ("R13", "Liq", "S_aa"): 0,
            ("R13", "Liq", "S_fa"): 0,
            ("R13", "Liq", "S_va"): 0,
            ("R13", "Liq", "S_bu"): 0,
            ("R13", "Liq", "S_pro"): 0,
            ("R13", "Liq", "S_ac"): 0,
            ("R13", "Liq", "S_h2"): 0,
            ("R13", "Liq", "S_ch4"): 0,
            ("R13", "Liq", "S_IC"): (
                self.Ci["X_aa"]
                - self.f_ch_xb * self.Ci["X_ch"]
                - self.f_pr_xb * self.Ci["X_pr"]
                - self.f_li_xb * self.Ci["X_li"]
                - self.f_xi_xb * self.Ci["X_I"]
            )
            * mw_c,
            ("R13", "Liq", "S_IN"): (
                self.Ni["X_aa"]
                - self.f_pr_xb * self.Ni["X_pr"]
                - self.f_xi_xb * self.Ni["X_I"]
            )
            * mw_n,
            ("R13", "Liq", "S_IP"): (
                self.Pi["X_aa"]
                - self.f_li_xb * self.Pi["X_li"]
                - self.f_xi_xb * self.Pi["X_I"]
            )
            * mw_p,
            ("R13", "Liq", "S_I"): 0,
            ("R13", "Liq", "X_ch"): self.f_ch_xb,
            ("R13", "Liq", "X_pr"): self.f_pr_xb,
            ("R13", "Liq", "X_li"): self.f_li_xb,
            ("R13", "Liq", "X_su"): 0,
            ("R13", "Liq", "X_aa"): -1,
            ("R13", "Liq", "X_fa"): 0,
            ("R13", "Liq", "X_c4"): 0,
            ("R13", "Liq", "X_pro"): 0,
            ("R13", "Liq", "X_ac"): 0,
            ("R13", "Liq", "X_h2"): 0,
            ("R13", "Liq", "X_I"): self.f_xi_xb,
            # R14: Decay of X_fa
            ("R14", "Liq", "H2O"): 0,
            ("R14", "Liq", "S_su"): 0,
            ("R14", "Liq", "S_aa"): 0,
            ("R14", "Liq", "S_fa"): 0,
            ("R14", "Liq", "S_va"): 0,
            ("R14", "Liq", "S_bu"): 0,
            ("R14", "Liq", "S_pro"): 0,
            ("R14", "Liq", "S_ac"): 0,
            ("R14", "Liq", "S_h2"): 0,
            ("R14", "Liq", "S_ch4"): 0,
            ("R14", "Liq", "S_IC"): (
                self.Ci["X_fa"]
                - self.f_ch_xb * self.Ci["X_ch"]
                - self.f_pr_xb * self.Ci["X_pr"]
                - self.f_li_xb * self.Ci["X_li"]
                - self.f_xi_xb * self.Ci["X_I"]
            )
            * mw_c,
            ("R14", "Liq", "S_IN"): (
                self.Ni["X_fa"]
                - self.f_pr_xb * self.Ni["X_pr"]
                - self.f_xi_xb * self.Ni["X_I"]
            )
            * mw_n,
            ("R14", "Liq", "S_IP"): (
                self.Pi["X_fa"]
                - self.f_li_xb * self.Pi["X_li"]
                - self.f_xi_xb * self.Pi["X_I"]
            )
            * mw_p,
            ("R14", "Liq", "S_I"): 0,
            ("R14", "Liq", "X_ch"): self.f_ch_xb,
            ("R14", "Liq", "X_pr"): self.f_pr_xb,
            ("R14", "Liq", "X_li"): self.f_li_xb,
            ("R14", "Liq", "X_su"): 0,
            ("R14", "Liq", "X_aa"): 0,
            ("R14", "Liq", "X_fa"): -1,
            ("R14", "Liq", "X_c4"): 0,
            ("R14", "Liq", "X_pro"): 0,
            ("R14", "Liq", "X_ac"): 0,
            ("R14", "Liq", "X_h2"): 0,
            ("R14", "Liq", "X_I"): self.f_xi_xb,
            # R15: Decay of X_c4
            ("R15", "Liq", "H2O"): 0,
            ("R15", "Liq", "S_su"): 0,
            ("R15", "Liq", "S_aa"): 0,
            ("R15", "Liq", "S_fa"): 0,
            ("R15", "Liq", "S_va"): 0,
            ("R15", "Liq", "S_bu"): 0,
            ("R15", "Liq", "S_pro"): 0,
            ("R15", "Liq", "S_ac"): 0,
            ("R15", "Liq", "S_h2"): 0,
            ("R15", "Liq", "S_ch4"): 0,
            ("R15", "Liq", "S_IC"): (
                self.Ci["X_c4"]
                - self.f_ch_xb * self.Ci["X_ch"]
                - self.f_pr_xb * self.Ci["X_pr"]
                - self.f_li_xb * self.Ci["X_li"]
                - self.f_xi_xb * self.Ci["X_I"]
            )
            * mw_c,
            ("R15", "Liq", "S_IN"): (
                self.Ni["X_c4"]
                - self.f_pr_xb * self.Ni["X_pr"]
                - self.f_xi_xb * self.Ni["X_I"]
            )
            * mw_n,
            ("R15", "Liq", "S_IP"): (
                self.Pi["X_c4"]
                - self.f_li_xb * self.Pi["X_li"]
                - self.f_xi_xb * self.Pi["X_I"]
            )
            * mw_p,
            ("R15", "Liq", "S_I"): 0,
            ("R15", "Liq", "X_ch"): self.f_ch_xb,
            ("R15", "Liq", "X_pr"): self.f_pr_xb,
            ("R15", "Liq", "X_li"): self.f_li_xb,
            ("R15", "Liq", "X_su"): 0,
            ("R15", "Liq", "X_aa"): 0,
            ("R15", "Liq", "X_fa"): 0,
            ("R15", "Liq", "X_c4"): -1,
            ("R15", "Liq", "X_pro"): 0,
            ("R15", "Liq", "X_ac"): 0,
            ("R15", "Liq", "X_h2"): 0,
            ("R15", "Liq", "X_I"): self.f_xi_xb,
            # R16: Decay of X_pro
            ("R16", "Liq", "H2O"): 0,
            ("R16", "Liq", "S_su"): 0,
            ("R16", "Liq", "S_aa"): 0,
            ("R16", "Liq", "S_fa"): 0,
            ("R16", "Liq", "S_va"): 0,
            ("R16", "Liq", "S_bu"): 0,
            ("R16", "Liq", "S_pro"): 0,
            ("R16", "Liq", "S_ac"): 0,
            ("R16", "Liq", "S_h2"): 0,
            ("R16", "Liq", "S_ch4"): 0,
            ("R16", "Liq", "S_IC"): (
                self.Ci["X_pro"]
                - self.f_ch_xb * self.Ci["X_ch"]
                - self.f_pr_xb * self.Ci["X_pr"]
                - self.f_li_xb * self.Ci["X_li"]
                - self.f_xi_xb * self.Ci["X_I"]
            )
            * mw_c,
            ("R16", "Liq", "S_IN"): (
                self.Ni["X_pro"]
                - self.f_pr_xb * self.Ni["X_pr"]
                - self.f_xi_xb * self.Ni["X_I"]
            )
            * mw_n,
            ("R16", "Liq", "S_IP"): (
                self.Pi["X_pro"]
                - self.f_li_xb * self.Pi["X_li"]
                - self.f_xi_xb * self.Pi["X_I"]
            )
            * mw_p,
            ("R16", "Liq", "S_I"): 0,
            ("R16", "Liq", "X_ch"): self.f_ch_xb,
            ("R16", "Liq", "X_pr"): self.f_pr_xb,
            ("R16", "Liq", "X_li"): self.f_li_xb,
            ("R16", "Liq", "X_su"): 0,
            ("R16", "Liq", "X_aa"): 0,
            ("R16", "Liq", "X_fa"): 0,
            ("R16", "Liq", "X_c4"): 0,
            ("R16", "Liq", "X_pro"): -1,
            ("R16", "Liq", "X_ac"): 0,
            ("R16", "Liq", "X_h2"): 0,
            ("R16", "Liq", "X_I"): self.f_xi_xb,
            # R17: Decay of X_ac
            ("R17", "Liq", "H2O"): 0,
            ("R17", "Liq", "S_su"): 0,
            ("R17", "Liq", "S_aa"): 0,
            ("R17", "Liq", "S_fa"): 0,
            ("R17", "Liq", "S_va"): 0,
            ("R17", "Liq", "S_bu"): 0,
            ("R17", "Liq", "S_pro"): 0,
            ("R17", "Liq", "S_ac"): 0,
            ("R17", "Liq", "S_h2"): 0,
            ("R17", "Liq", "S_ch4"): 0,
            ("R17", "Liq", "S_IC"): (
                self.Ci["X_ac"]
                - self.f_ch_xb * self.Ci["X_ch"]
                - self.f_pr_xb * self.Ci["X_pr"]
                - self.f_li_xb * self.Ci["X_li"]
                - self.f_xi_xb * self.Ci["X_I"]
            )
            * mw_c,
            ("R17", "Liq", "S_IN"): (
                self.Ni["X_ac"]
                - self.f_pr_xb * self.Ni["X_pr"]
                - self.f_xi_xb * self.Ni["X_I"]
            )
            * mw_n,
            ("R17", "Liq", "S_IP"): (
                self.Pi["X_ac"]
                - self.f_li_xb * self.Pi["X_li"]
                - self.f_xi_xb * self.Pi["X_I"]
            )
            * mw_p,
            ("R17", "Liq", "S_I"): 0,
            ("R17", "Liq", "X_ch"): self.f_ch_xb,
            ("R17", "Liq", "X_pr"): self.f_pr_xb,
            ("R17", "Liq", "X_li"): self.f_li_xb,
            ("R17", "Liq", "X_su"): 0,
            ("R17", "Liq", "X_aa"): 0,
            ("R17", "Liq", "X_fa"): 0,
            ("R17", "Liq", "X_c4"): 0,
            ("R17", "Liq", "X_pro"): 0,
            ("R17", "Liq", "X_ac"): -1,
            ("R17", "Liq", "X_h2"): 0,
            ("R17", "Liq", "X_I"): self.f_xi_xb,
            # R18: Decay of X_h2
            ("R18", "Liq", "H2O"): 0,
            ("R18", "Liq", "S_su"): 0,
            ("R18", "Liq", "S_aa"): 0,
            ("R18", "Liq", "S_fa"): 0,
            ("R18", "Liq", "S_va"): 0,
            ("R18", "Liq", "S_bu"): 0,
            ("R18", "Liq", "S_pro"): 0,
            ("R18", "Liq", "S_ac"): 0,
            ("R18", "Liq", "S_h2"): 0,
            ("R18", "Liq", "S_ch4"): 0,
            ("R18", "Liq", "S_IC"): (
                self.Ci["X_h2"]
                - self.f_ch_xb * self.Ci["X_ch"]
                - self.f_pr_xb * self.Ci["X_pr"]
                - self.f_li_xb * self.Ci["X_li"]
                - self.f_xi_xb * self.Ci["X_I"]
            )
            * mw_c,
            ("R18", "Liq", "S_IN"): (
                self.Ni["X_h2"]
                - self.f_pr_xb * self.Ni["X_pr"]
                - self.f_xi_xb * self.Ni["X_I"]
            )
            * mw_n,
            ("R18", "Liq", "S_IP"): (
                self.Pi["X_h2"]
                - self.f_li_xb * self.Pi["X_li"]
                - self.f_xi_xb * self.Pi["X_I"]
            )
            * mw_p,
            ("R18", "Liq", "S_I"): 0,
            ("R18", "Liq", "X_ch"): self.f_ch_xb,
            ("R18", "Liq", "X_pr"): self.f_pr_xb,
            ("R18", "Liq", "X_li"): self.f_li_xb,
            ("R18", "Liq", "X_su"): 0,
            ("R18", "Liq", "X_aa"): 0,
            ("R18", "Liq", "X_fa"): 0,
            ("R18", "Liq", "X_c4"): 0,
            ("R18", "Liq", "X_pro"): 0,
            ("R18", "Liq", "X_ac"): 0,
            ("R18", "Liq", "X_h2"): -1,
            ("R18", "Liq", "X_I"): self.f_xi_xb,
        }

        # TODO: Update s_ic_rxns list and add similar code for S_IN and S_IP

        # s_ic_rxns = ["R5", "R6", "R10", "R11", "R12"]
        #
        # for R in s_ic_rxns:
        #     self.rate_reaction_stoichiometry[R, "Liq", "S_IC"] = -sum(
        #         self.Ci[S] * self.rate_reaction_stoichiometry[R, "Liq", S] * mw_c
        #         for S in Ci_dict.keys()
        #         if S != "S_IC"
        #     )

        for R in self.rate_reaction_idx:
            self.rate_reaction_stoichiometry[R, "Liq", "S_cat"] = 0
            self.rate_reaction_stoichiometry[R, "Liq", "S_an"] = 0

        # Fix all the variables we just created
        for v in self.component_objects(pyo.Var, descend_into=False):
            v.fix()

    @classmethod
    def define_metadata(cls, obj):
        obj.add_properties(
            {
                "conc_mol_co2": {"method": "_rxn_rate"},
                "reaction_rate": {"method": "_rxn_rate"},
                "I": {"method": "_I"},
            }
        )
        obj.add_default_units(
            {
                "time": pyo.units.s,
                "length": pyo.units.m,
                "mass": pyo.units.kg,
                "amount": pyo.units.kmol,
                "temperature": pyo.units.K,
            }
        )


# TODO: Update the class names below
class _ModifiedADM1ReactionBlock(ReactionBlockBase):
    """
    This Class contains methods which should be applied to Reaction Blocks as a
    whole, rather than individual elements of indexed Reaction Blocks.
    """

    def initialize(self, outlvl=idaeslog.NOTSET, **kwargs):
        """
        Initialization routine for reaction package.

        Keyword Arguments:
            outlvl : sets output level of initialization routine

        Returns:
            None
        """
        init_log = idaeslog.getInitLogger(self.name, outlvl, tag="properties")
        init_log.info("Initialization Complete.")


@declare_process_block_class(
    "ModifiedADM1ReactionBlock", block_class=_ModifiedADM1ReactionBlock
)
class ModifiedADM1ReactionBlockData(ReactionBlockDataBase):
    """
    ReactionBlock for ADM1.
    """

    def build(self):
        """
        Callable method for Block construction
        """
        super().build()

        # Create references to state vars
        # Concentration
        add_object_reference(self, "conc_mass_comp_ref", self.state_ref.conc_mass_comp)
        add_object_reference(self, "temperature", self.state_ref.temperature)

        # Initial values of rates of reaction [2]
        self.rates = {
            "R1": 3.235e-06,
            "R2": 1.187e-05,
            "R3": 3.412e-06,
            "R4": 3.404e-06,
            "R5": 1.187e-05,
            "R6": 3.185e-06,
            "R7": 2.505e-06,
            "R8": 3.230e-06,
            "R9": 2.636e-06,
            "R10": 1.220e-05,
            "R11": 4.184e-06,
            "R12": 9.726e-08,
            "R13": 2.730e-07,
            "R14": 5.626e-08,
            "R15": 9.998e-08,
            "R16": 3.178e-08,
            "R17": 1.761e-07,
            "R18": 7.338e-08,
        }

    # Rate of reaction method
    def _rxn_rate(self):
        self.reaction_rate = pyo.Var(
            self.params.rate_reaction_idx,
            initialize=self.rates,
            bounds=(1e-9, 1e-4),
            doc="Rate of reaction",
            units=pyo.units.kg / pyo.units.m**3 / pyo.units.s,
        )
        self.KW = pyo.Var(
            initialize=2.08e-14,
            units=(pyo.units.kmol / pyo.units.m**3) ** 2,
            domain=pyo.PositiveReals,
            doc="Water dissociation constant",
        )
        self.K_a_co2 = pyo.Var(
            initialize=4.94e-7,
            units=pyo.units.kmol / pyo.units.m**3,
            domain=pyo.PositiveReals,
            doc="Carbon dioxide acid-base equilibrium constant",
        )
        self.K_a_IN = pyo.Var(
            initialize=1.11e-9,
            units=pyo.units.kmol / pyo.units.m**3,
            domain=pyo.PositiveReals,
            doc="Inorganic nitrogen acid-base equilibrium constant",
        )
        self.conc_mass_va = pyo.Var(
            initialize=0.01159624,
            domain=pyo.NonNegativeReals,
            doc="molar concentration of va-",
            units=pyo.units.kg / pyo.units.m**3,
        )
        self.conc_mass_bu = pyo.Var(
            initialize=0.0132208,
            domain=pyo.NonNegativeReals,
            doc="molar concentration of bu-",
            units=pyo.units.kg / pyo.units.m**3,
        )
        self.conc_mass_pro = pyo.Var(
            initialize=0.015742,
            domain=pyo.NonNegativeReals,
            doc="molar concentration of pro-",
            units=pyo.units.kg / pyo.units.m**3,
        )
        self.conc_mass_ac = pyo.Var(
            initialize=0.1972,
            domain=pyo.NonNegativeReals,
            doc="molar concentration of ac-",
            units=pyo.units.kg / pyo.units.m**3,
        )
        self.conc_mol_hco3 = pyo.Var(
            initialize=0.142777,
            domain=pyo.NonNegativeReals,
            doc="molar concentration of hco3",
            units=pyo.units.kmol / pyo.units.m**3,
        )
        self.conc_mol_nh3 = pyo.Var(
            initialize=0.004,
            domain=pyo.NonNegativeReals,
            doc="molar concentration of nh3",
            units=pyo.units.kmol / pyo.units.m**3,
        )
        self.conc_mol_co2 = pyo.Var(
            initialize=0.0099,
            domain=pyo.NonNegativeReals,
            doc="molar concentration of co2",
            units=pyo.units.kmol / pyo.units.m**3,
        )
        self.conc_mol_nh4 = pyo.Var(
            initialize=0.1261,
            domain=pyo.NonNegativeReals,
            doc="molar concentration of nh4",
            units=pyo.units.kmol / pyo.units.m**3,
        )
        self.S_H = pyo.Var(
            initialize=3.4e-8,
            domain=pyo.NonNegativeReals,
            doc="molar concentration of H",
            units=pyo.units.kmol / pyo.units.m**3,
        )
        self.S_OH = pyo.Var(
            initialize=3.4e-8,
            domain=pyo.NonNegativeReals,
            doc="molar concentration of OH",
            units=pyo.units.kmol / pyo.units.m**3,
        )
        self.Z_h2s = pyo.Var(
            initialize=0,
            domain=pyo.NonNegativeReals,
            doc="Reference component mass concentrations of hydrogen sulfide",
            units=pyo.units.kg / pyo.units.m**3,
        )

        # Equation from [2]
        def Dissociation_rule(self, t):
            return (
                self.KW
                == (
                    1e-14
                    * pyo.exp(
                        55900
                        / pyo.units.mole
                        * pyo.units.joule
                        / (Constants.gas_constant)
                        * ((1 / self.params.temperature_ref) - (1 / self.temperature))
                    )
                )
                * pyo.units.kilomole**2
                / pyo.units.meter**6
            )

        self.Dissociation = pyo.Constraint(
            rule=Dissociation_rule,
            doc="Dissociation constant constraint",
        )

        # Equation from [2]
        def CO2_acid_base_equilibrium_rule(self, t):
            return (
                self.K_a_co2
                == (
                    4.46684e-07
                    * pyo.exp(
                        7646
                        / pyo.units.mole
                        * pyo.units.joule
                        / (Constants.gas_constant)
                        * ((1 / self.params.temperature_ref) - (1 / self.temperature))
                    )
                )
                * pyo.units.kilomole
                / pyo.units.meter**3
            )

        self.CO2_acid_base_equilibrium = pyo.Constraint(
            rule=CO2_acid_base_equilibrium_rule,
            doc="Carbon dioxide acid-base equilibrium constraint",
        )

        # Equation from [2]
        def IN_acid_base_equilibrium_rule(self, t):
            return (
                self.K_a_IN
                == (
                    5.62341e-10
                    * pyo.exp(
                        51965
                        / pyo.units.mole
                        * pyo.units.joule
                        / (Constants.gas_constant)
                        * ((1 / self.params.temperature_ref) - (1 / self.temperature))
                    )
                )
                * pyo.units.kilomole
                / pyo.units.meter**3
            )

        self.IN_acid_base_equilibrium = pyo.Constraint(
            rule=IN_acid_base_equilibrium_rule,
            doc="Nitrogen acid-base equilibrium constraint",
        )

        mw_n = 14 * pyo.units.kg / pyo.units.kmol
        mw_p = 31 * pyo.units.kg / pyo.units.kmol

        def concentration_of_va_rule(self):
            return self.conc_mass_va == self.params.K_a_va * self.conc_mass_comp_ref[
                "S_va"
            ] / (self.params.K_a_va + self.S_H)

        self.concentration_of_va = pyo.Constraint(
            rule=concentration_of_va_rule,
            doc="constraint concentration of va-",
        )

        def concentration_of_bu_rule(self):
            return self.conc_mass_bu == self.params.K_a_bu * self.conc_mass_comp_ref[
                "S_bu"
            ] / (self.params.K_a_bu + self.S_H)

        self.concentration_of_bu = pyo.Constraint(
            rule=concentration_of_bu_rule,
            doc="constraint concentration of bu-",
        )

        def concentration_of_pro_rule(self):
            return self.conc_mass_pro == self.params.K_a_pro * self.conc_mass_comp_ref[
                "S_pro"
            ] / (self.params.K_a_pro + self.S_H)

        self.concentration_of_pro = pyo.Constraint(
            rule=concentration_of_pro_rule,
            doc="constraint concentration of pro-",
        )

        def concentration_of_ac_rule(self):
            return self.conc_mass_ac == self.params.K_a_ac * self.conc_mass_comp_ref[
                "S_ac"
            ] / (self.params.K_a_ac + self.S_H)

        self.concentration_of_ac = pyo.Constraint(
            rule=concentration_of_ac_rule,
            doc="constraint concentration of ac-",
        )

        def concentration_of_hco3_rule(self):
            return self.conc_mol_hco3 == self.K_a_co2 * (
                self.conc_mass_comp_ref["S_IC"] / (12 * pyo.units.kg / pyo.units.kmol)
            ) / (self.K_a_co2 + self.S_H)

        self.concentration_of_hco3 = pyo.Constraint(
            rule=concentration_of_hco3_rule,
            doc="constraint concentration of hco3",
        )

        def concentration_of_nh3_rule(self):
            return self.conc_mol_nh3 == self.K_a_IN * (
                self.conc_mass_comp_ref["S_IN"] / (14 * pyo.units.kg / pyo.units.kmol)
            ) / (self.K_a_IN + self.S_H)

        self.concentration_of_nh3 = pyo.Constraint(
            rule=concentration_of_nh3_rule,
            doc="constraint concentration of nh3",
        )

        # TO DO: use correct conversion number
        def concentration_of_co2_rule(self):
            return (
                self.conc_mol_co2
                == self.conc_mass_comp_ref["S_IC"]
                / (12 * pyo.units.kg / pyo.units.kmol)
                - self.conc_mol_hco3
            )

        self.concentration_of_co2 = pyo.Constraint(
            rule=concentration_of_co2_rule,
            doc="constraint concentration of co2",
        )

        def concentration_of_nh4_rule(self):
            return (
                self.conc_mol_nh4
                == self.conc_mass_comp_ref["S_IN"]
                / (14 * pyo.units.kg / pyo.units.kmol)
                - self.conc_mol_nh3
            )

        self.concentration_of_nh4 = pyo.Constraint(
            rule=concentration_of_nh4_rule,
            doc="constraint concentration of pro-",
        )

        def S_OH_rule(self):
            return self.S_OH == self.KW / self.S_H

        self.S_OH_cons = pyo.Constraint(
            rule=S_OH_rule,
            doc="constraint concentration of OH",
        )

        def S_H_rule(self):
            return (
                self.state_ref.cations
                + self.conc_mol_nh4
                + self.S_H
                - self.conc_mol_hco3
                - self.conc_mass_ac / (64 * pyo.units.kg / pyo.units.kmol)
                - self.conc_mass_pro / (112 * pyo.units.kg / pyo.units.kmol)
                - self.conc_mass_bu / (160 * pyo.units.kg / pyo.units.kmol)
                - self.conc_mass_va / (208 * pyo.units.kg / pyo.units.kmol)
                - self.S_OH
                - self.state_ref.anions
                == 0
            )

        self.S_H_cons = pyo.Constraint(
            rule=S_H_rule,
            doc="constraint concentration of pro-",
        )

        def rule_pH(self):
            return -pyo.log10(self.S_H / pyo.units.kmol * pyo.units.m**3)

        self.pH = pyo.Expression(rule=rule_pH, doc="pH of solution")

        def rule_I_IN_lim(self):
            return 1 / (
                1 + self.params.K_S_IN / (self.conc_mass_comp_ref["S_IN"] / mw_n)
            )

        self.I_IN_lim = pyo.Expression(
            rule=rule_I_IN_lim,
            doc="Inhibition function related to secondary substrate; inhibit uptake when inorganic nitrogen S_IN~ 0",
        )

        def rule_I_IP_lim(self):
            return 1 / (
                1 + self.params.K_S_IP / (self.conc_mass_comp_ref["S_IP"] / mw_p)
            )

        self.I_IP_lim = pyo.Expression(
            rule=rule_I_IP_lim,
            doc="Inhibition function related to secondary substrate; inhibit uptake when inorganic phosphorus S_IP~ 0",
        )

        def rule_I_h2_fa(self):
            return 1 / (1 + self.conc_mass_comp_ref["S_h2"] / self.params.K_I_h2_fa)

        self.I_h2_fa = pyo.Expression(
            rule=rule_I_h2_fa,
            doc="hydrogen inhibition attributed to long chain fatty acids",
        )

        def rule_I_h2_c4(self):
            return 1 / (1 + self.conc_mass_comp_ref["S_h2"] / self.params.K_I_h2_c4)

        self.I_h2_c4 = pyo.Expression(
            rule=rule_I_h2_c4,
            doc="hydrogen inhibition attributed to valerate and butyrate uptake",
        )

        def rule_I_h2_pro(self):
            return 1 / (1 + self.conc_mass_comp_ref["S_h2"] / self.params.K_I_h2_pro)

        self.I_h2_pro = pyo.Expression(
            rule=rule_I_h2_pro,
            doc="hydrogen inhibition attributed to propionate uptake",
        )

        # TODO: revisit Z_h2s values and if we have ref state for S_h2s
        def rule_I_h2s_ac(self):
            return 1 / (1 + self.Z_h2s / self.params.K_I_h2s_ac)

        self.I_h2s_ac = pyo.Expression(
            rule=rule_I_h2s_ac,
            doc="hydrogen sulfide inhibition attributed to acetate uptake",
        )

        def rule_I_h2s_c4(self):
            return 1 / (1 + self.Z_h2s / self.params.K_I_h2s_c4)

        self.I_h2s_c4 = pyo.Expression(
            rule=rule_I_h2s_c4,
            doc="hydrogen sulfide inhibition attributed to valerate and butyrate uptake",
        )

        def rule_I_h2s_h2(self):
            return 1 / (1 + self.Z_h2s / self.params.K_I_h2s_h2)

        self.I_h2s_h2 = pyo.Expression(
            rule=rule_I_h2s_h2,
            doc="hydrogen sulfide inhibition attributed to hydrogen uptake",
        )

        def rule_I_h2s_pro(self):
            return 1 / (1 + self.Z_h2s / self.params.K_I_h2s_pro)

        self.I_h2s_pro = pyo.Expression(
            rule=rule_I_h2s_pro,
            doc="hydrogen sulfide inhibition attributed to propionate uptake",
        )

        def rule_I_nh3(self):
            return 1 / (1 + self.conc_mol_nh3 / self.params.K_I_nh3)

        self.I_nh3 = pyo.Expression(
            rule=rule_I_nh3, doc="ammonia inibition attributed to acetate uptake"
        )

        def rule_I_pH_aa(self):
            return pyo.Expr_if(
                self.pH > self.params.pH_UL_aa,
                1,
                pyo.exp(
                    -3
                    * (
                        (self.pH - self.params.pH_UL_aa)
                        / (self.params.pH_UL_aa - self.params.pH_LL_aa)
                    )
                    ** 2
                ),
            )

        self.I_pH_aa = pyo.Expression(
            rule=rule_I_pH_aa,
            doc="pH inhibition of amino-acid-utilizing microorganisms",
        )

        def rule_I_pH_ac(self):
            return pyo.Expr_if(
                self.pH > self.params.pH_UL_ac,
                1,
                pyo.exp(
                    -3
                    * (
                        (self.pH - self.params.pH_UL_ac)
                        / (self.params.pH_UL_ac - self.params.pH_LL_ac)
                    )
                    ** 2
                ),
            )

        self.I_pH_ac = pyo.Expression(
            rule=rule_I_pH_ac, doc="pH inhibition of acetate-utilizing microorganisms"
        )

        def rule_I_pH_h2(self):
            return pyo.Expr_if(
                self.pH > self.params.pH_UL_h2,
                1,
                pyo.exp(
                    -3
                    * (
                        (self.pH - self.params.pH_UL_h2)
                        / (self.params.pH_UL_h2 - self.params.pH_LL_h2)
                    )
                    ** 2
                ),
            )

        self.I_pH_h2 = pyo.Expression(
            rule=rule_I_pH_h2, doc="pH inhibition of hydrogen-utilizing microorganisms"
        )

        def rule_I(self, r):
            if r == "R4" or r == "R5":
                return self.I_pH_aa * self.I_IN_lim * self.I_IP_lim
            elif r == "R6":
                return self.I_pH_aa * self.I_IN_lim * self.I_h2_fa * self.I_IP_lim
            elif r == "R7" or r == "R8":
                return self.I_pH_aa * self.I_IN_lim * self.I_h2_c4 * self.I_IP_lim
            elif r == "R9":
                return self.I_pH_aa * self.I_IN_lim * self.I_h2_pro * self.I_IP_lim
            elif r == "R10":
                return self.I_pH_ac * self.I_IN_lim * self.I_nh3 * self.I_IP_lim
            elif r == "R11":
                return self.I_pH_h2 * self.I_IN_lim * self.I_IP_lim
            else:
                raise BurntToast()

        self.I = pyo.Expression(
            [f"R{i}" for i in range(5, 13)],
            rule=rule_I,
            doc="Process inhibition functions",
        )

        try:

            def rate_expression_rule(b, r):
                if r == "R1":
                    # R1: Hydrolysis of carbohydrates
                    return b.reaction_rate[r] == pyo.units.convert(
                        b.params.k_hyd_ch * b.conc_mass_comp_ref["X_ch"],
                        to_units=pyo.units.kg / pyo.units.m**3 / pyo.units.s,
                    )
                elif r == "R2":
                    # R2: Hydrolysis of proteins
                    return b.reaction_rate[r] == pyo.units.convert(
                        b.params.k_hyd_pr * b.conc_mass_comp_ref["X_pr"],
                        to_units=pyo.units.kg / pyo.units.m**3 / pyo.units.s,
                    )
                elif r == "R3":
                    # R3: Hydrolysis of lipids
                    return b.reaction_rate[r] == pyo.units.convert(
                        b.params.k_hyd_li * b.conc_mass_comp_ref["X_li"],
                        to_units=pyo.units.kg / pyo.units.m**3 / pyo.units.s,
                    )
                elif r == "R4":
                    # R4: Uptake of sugars
                    return b.reaction_rate[r] == pyo.units.convert(
                        b.params.k_m_su
                        * b.conc_mass_comp_ref["S_su"]
                        / (b.params.K_S_su + b.conc_mass_comp_ref["S_su"])
                        * b.conc_mass_comp_ref["X_su"]
                        * b.I[r],
                        to_units=pyo.units.kg / pyo.units.m**3 / pyo.units.s,
                    )
                elif r == "R5":
                    # R5: Uptake of amino acids
                    return b.reaction_rate[r] == pyo.units.convert(
                        b.params.k_m_aa
                        * b.conc_mass_comp_ref["S_aa"]
                        / (b.params.K_S_aa + b.conc_mass_comp_ref["S_aa"])
                        * b.conc_mass_comp_ref["X_aa"]
                        * b.I[r],
                        to_units=pyo.units.kg / pyo.units.m**3 / pyo.units.s,
                    )
                elif r == "R6":
                    # R6: Uptake of long chain fatty acids (LCFAs)
                    return b.reaction_rate[r] == pyo.units.convert(
                        b.params.k_m_fa
                        * b.conc_mass_comp_ref["S_fa"]
                        / (b.params.K_S_fa + b.conc_mass_comp_ref["S_fa"])
                        * b.conc_mass_comp_ref["X_fa"]
                        * b.I[r],
                        to_units=pyo.units.kg / pyo.units.m**3 / pyo.units.s,
                    )
                elif r == "R7":
                    # R7: Uptake of valerate
                    return b.reaction_rate[r] == pyo.units.convert(
                        b.params.k_m_c4
                        * b.conc_mass_comp_ref["S_va"]
                        / (b.params.K_S_c4 + b.conc_mass_comp_ref["S_va"])
                        * b.conc_mass_comp_ref["X_c4"]
                        * (
                            b.conc_mass_comp_ref["S_va"]
                            / (
                                b.conc_mass_comp_ref["S_va"]
                                + b.conc_mass_comp_ref["S_bu"]
                            )
                        )
                        * b.I[r]
                        * b.params.I_h2s_c4,
                        to_units=pyo.units.kg / pyo.units.m**3 / pyo.units.s,
                    )
                elif r == "R8":
                    # R8:  Uptake of butyrate
                    return b.reaction_rate[r] == pyo.units.convert(
                        b.params.k_m_c4
                        * b.conc_mass_comp_ref["S_bu"]
                        / (b.params.K_S_c4 + b.conc_mass_comp_ref["S_bu"])
                        * b.conc_mass_comp_ref["X_c4"]
                        * (
                            b.conc_mass_comp_ref["S_bu"]
                            / (
                                b.conc_mass_comp_ref["S_va"]
                                + b.conc_mass_comp_ref["S_bu"]
                            )
                        )
                        * b.I[r]
                        * b.params.I_h2s_c4,
                        to_units=pyo.units.kg / pyo.units.m**3 / pyo.units.s,
                    )
                elif r == "R9":
                    # R9: Uptake of propionate
                    return b.reaction_rate[r] == pyo.units.convert(
                        b.params.k_m_pro
                        * b.conc_mass_comp_ref["S_pro"]
                        / (b.params.K_S_pro + b.conc_mass_comp_ref["S_pro"])
                        * b.conc_mass_comp_ref["X_pro"]
                        * b.I[r]
                        * b.params.I_h2s_pro,
                        to_units=pyo.units.kg / pyo.units.m**3 / pyo.units.s,
                    )
                elif r == "R10":
                    # R10: Uptake of acetate
                    return b.reaction_rate[r] == pyo.units.convert(
                        b.params.k_m_ac
                        * b.conc_mass_comp_ref["S_ac"]
                        / (b.params.K_S_ac + b.conc_mass_comp_ref["S_ac"])
                        * b.conc_mass_comp_ref["X_ac"]
                        * b.I[r]
                        * b.params.I_h2s_ac,
                        to_units=pyo.units.kg / pyo.units.m**3 / pyo.units.s,
                    )
                elif r == "R11":
                    # R11: Uptake of hydrogen
                    return b.reaction_rate[r] == pyo.units.convert(
                        b.params.k_m_h2
                        * b.conc_mass_comp_ref["S_h2"]
                        / (b.params.K_S_h2 + b.conc_mass_comp_ref["S_h2"])
                        * b.conc_mass_comp_ref["X_h2"]
                        * b.I[r]
                        * b.params.I_h2s_h2,
                        to_units=pyo.units.kg / pyo.units.m**3 / pyo.units.s,
                    )
                elif r == "R12":
                    # R12: Decay of X_su
                    return b.reaction_rate[r] == pyo.units.convert(
                        b.params.k_dec_X_su * b.conc_mass_comp_ref["X_su"],
                        to_units=pyo.units.kg / pyo.units.m**3 / pyo.units.s,
                    )
                elif r == "R13":
                    # R13: Decay of X_aa
                    return b.reaction_rate[r] == pyo.units.convert(
                        b.params.k_dec_X_aa * b.conc_mass_comp_ref["X_aa"],
                        to_units=pyo.units.kg / pyo.units.m**3 / pyo.units.s,
                    )
                elif r == "R14":
                    # R14: Decay of X_fa
                    return b.reaction_rate[r] == pyo.units.convert(
                        b.params.k_dec_X_fa * b.conc_mass_comp_ref["X_fa"],
                        to_units=pyo.units.kg / pyo.units.m**3 / pyo.units.s,
                    )
                elif r == "R15":
                    # R15: Decay of X_c4
                    return b.reaction_rate[r] == pyo.units.convert(
                        b.params.k_dec_X_c4 * b.conc_mass_comp_ref["X_c4"],
                        to_units=pyo.units.kg / pyo.units.m**3 / pyo.units.s,
                    )
                elif r == "R16":
                    # R16: Decay of X_pro
                    return b.reaction_rate[r] == pyo.units.convert(
                        b.params.k_dec_X_pro * b.conc_mass_comp_ref["X_pro"],
                        to_units=pyo.units.kg / pyo.units.m**3 / pyo.units.s,
                    )
                elif r == "R17":
                    # R17: Decay of X_ac
                    return b.reaction_rate[r] == pyo.units.convert(
                        b.params.k_dec_X_ac * b.conc_mass_comp_ref["X_ac"],
                        to_units=pyo.units.kg / pyo.units.m**3 / pyo.units.s,
                    )
                elif r == "R18":
                    # R18: Decay of X_h2
                    return b.reaction_rate[r] == (
                        pyo.units.convert(b.params.k_dec_X_h2, to_units=1 / pyo.units.s)
                        * b.conc_mass_comp_ref["X_h2"]
                    )
                else:
                    raise BurntToast()

            self.rate_expression = pyo.Constraint(
                self.params.rate_reaction_idx,
                rule=rate_expression_rule,
                doc="ADM1 rate expressions",
            )

        except AttributeError:
            # If constraint fails, clean up so that DAE can try again later
            self.del_component(self.reaction_rate)
            self.del_component(self.rate_expression)
            raise

        iscale.set_scaling_factor(self.reaction_rate, 1e6)
        iscale.set_scaling_factor(self.conc_mass_va, 1e2)
        iscale.set_scaling_factor(self.conc_mass_bu, 1e2)
        iscale.set_scaling_factor(self.conc_mass_pro, 1e2)
        iscale.set_scaling_factor(self.conc_mass_ac, 1e1)
        iscale.set_scaling_factor(self.conc_mol_hco3, 1e1)
        iscale.set_scaling_factor(self.conc_mol_nh3, 1e1)
        iscale.set_scaling_factor(self.conc_mol_co2, 1e1)
        iscale.set_scaling_factor(self.conc_mol_nh4, 1e1)
        iscale.set_scaling_factor(self.S_H, 1e7)
        iscale.set_scaling_factor(self.S_OH, 1e8)
        iscale.set_scaling_factor(self.KW, 1e14)
        iscale.set_scaling_factor(self.K_a_co2, 1e7)
        iscale.set_scaling_factor(self.K_a_IN, 1e9)

    def get_reaction_rate_basis(self):
        return MaterialFlowBasis.mass

    def calculate_scaling_factors(self):
        super().calculate_scaling_factors()

        for i, c in self.rate_expression.items():
            # TODO: Need to work out how to calculate good scaling factors
            # instead of a fixed 1e3.
            iscale.constraint_scaling_transform(c, 1e5, overwrite=True)
