""""""

import subprocess
import sys
from pathlib import Path

import pytest

MAIN_DIR = Path(__file__).parent.parent
TEST_DIR = MAIN_DIR / "test"
TEST_INPUT = TEST_DIR / "input"
TEST_OUT_DIR = TEST_DIR / "output"
EXE = MAIN_DIR / "qc_daily_final.py"


def test_run_l2b()->None:
    """Function used to test the l2b's run 
    """
    L2A_jm1=f"{TEST_INPUT}/eprofile_L2A_STRATFINDER_granada_chm15k-A_v01_20230630.nc" 
    L2A_j=f"{TEST_INPUT}/eprofile_L2A_STRATFINDER_granada_chm15k-A_v01_20230701.nc"
    L2A_jp1=f"{TEST_INPUT}/eprofile_L2A_STRATFINDER_granada_chm15k-A_v01_20230702.nc" 
    json=f"{TEST_INPUT}/settings_STRATfinder_granada_chm15k_A.json"
    values_qc=f"{MAIN_DIR}/values_qc.toml" 
    metadata_qc=f"{MAIN_DIR}/STRATFINDER_metadata.toml"
    output=f"{TEST_OUT_DIR}/eprofile_L2B_STRATFINDER_granada_chm15k-A_v01_20230701.nc"


    ret = subprocess.call(
        [
            sys.executable,
            EXE,
            L2A_jm1,
            L2A_j,
            L2A_jp1,
            json,
            values_qc,
            metadata_qc,
            output,
        ]
    )
    assert ret == 0