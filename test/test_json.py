import subprocess
import sys
from pathlib import Path

import pytest

MAIN_DIR = Path(__file__).parent.parent
TEST_DIR = MAIN_DIR / "test"
TEST_INPUT = TEST_DIR / "input"
TEST_OUT_DIR = TEST_DIR / "output"
EXE = MAIN_DIR / "plot_sites_json.py"


def test_run_json()->None:
    """Function used to test the l2b's run 
    """

    site="falkenberg" 
    input="/bdd/E-PROFILE/L2B_CONCAT/falkenberg" 
    month="2" 
    inst="chm15k" 
    inst_id="0" 
    version="v01"

    ret = subprocess.call(
        [
            sys.executable,
            EXE,
            site,
            input,
            month,
            TEST_OUT_DIR,
            inst,
            inst_id,
            version,
        ]
    )
    assert ret == 0