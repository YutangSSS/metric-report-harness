import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from pathlib import Path

import pytest

from harness.db import DATA_DIR, connect

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def con():
    if not (DATA_DIR / "aac_intakes.csv").exists():
        pytest.skip("public data not downloaded: run `uv run python scripts/fetch_data.py`")
    return connect()


@pytest.fixture(scope="session")
def oracle_stays():
    from oracle import load

    if not (DATA_DIR / "aac_intakes.csv").exists():
        pytest.skip("public data not downloaded")
    return load(DATA_DIR)


@pytest.fixture()
def tiny():
    return connect(FIXTURES / "tiny_intakes.csv", FIXTURES / "tiny_outcomes.csv")
