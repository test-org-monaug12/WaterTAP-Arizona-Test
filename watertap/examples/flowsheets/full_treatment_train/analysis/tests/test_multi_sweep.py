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
import pytest
from watertap.examples.flowsheets.full_treatment_train.analysis.multi_sweep import *

pytest_parameterize_list = []
# We are skipping cases 5 & 7 in order to keep the pytests times in check
for case_num in [1, 2, 3, 4, 6, 8, 9]:
    for ro_type in ['0D', '1D']:
        test_case = (case_num, ro_type)
        pytest_parameterize_list.append(test_case)

@pytest.mark.parametrize('case_num, RO_type', pytest_parameterize_list)
@pytest.mark.integration
@pytest.mark.xfail(reason="COSTING_UPDATE: needs costing update")
def test_multi_sweep(case_num, RO_type):
    nx = 1
    global_results, sweep_params = run_analysis(case_num, nx, RO_type, interp_nan_outputs=False)
