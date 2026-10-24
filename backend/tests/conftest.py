import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(scope="session")
def demo_db(tmp_path_factory):
    """A database populated by one full demo pipeline run."""
    path = tmp_path_factory.mktemp("db") / "demo.db"
    os.environ["MACRO_DATABASE_URL"] = f"sqlite:///{path}"
    os.environ["MACRO_LLM_ENABLED"] = "false"
    from macrodash.config import get_settings
    get_settings.cache_clear()
    from macrodash.pipeline import run
    payload = run(demo=True)
    return path, payload
