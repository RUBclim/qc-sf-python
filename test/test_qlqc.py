import subprocess
import sys
from pathlib import Path

import pytest

MAIN_DIR = Path(__file__).parent.parent
TEST_DIR = MAIN_DIR / "test"
TEST_INPUT = TEST_DIR / "input"
TEST_OUT_DIR = TEST_DIR / "output"
EXE = MAIN_DIR / "plot_daily.py"


def test_run_qlqc()->None:
    """Function used to test the l2b's run 
    """
    L2A_j=f"{TEST_INPUT}/eprofile_L2A_STRATFINDER_granada_chm15k-A_v01_20230701.nc"
    L2B_j=f"{TEST_INPUT}/eprofile_L2B_STRATFINDER_granada_chm15k-A_v01_20230701.nc" 
    output=f"{TEST_OUT_DIR}/eprofile_QLQC_STRATFINDER_granada_chm15k-A_v01_20230701.png"


    ret = subprocess.call(
        [
            sys.executable,
            EXE,
            L2A_j,
            L2B_j,
            output,
        ]
    )
    assert ret == 0