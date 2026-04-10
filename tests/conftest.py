from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest


TMP_ROOT = Path(__file__).resolve().parent / '_runtime_tmp'
TMP_ROOT.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def workspace_tmp_path() -> Path:
    path = TMP_ROOT / uuid.uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
