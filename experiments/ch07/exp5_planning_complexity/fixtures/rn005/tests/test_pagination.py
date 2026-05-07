import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.constants import MAX_PAGE_SIZE
from src.api import paginate
from src.cli import cmd_list_with_default
from src.repository import fetch_default_window


def test_paginate_default():
    items = list(range(200))
    page0 = paginate(items, 0)
    assert len(page0) == MAX_PAGE_SIZE


def test_paginate_caps():
    items = list(range(500))
    page0 = paginate(items, 0, size=999)
    assert len(page0) == MAX_PAGE_SIZE


def test_cmd_list_default():
    assert str(MAX_PAGE_SIZE) in cmd_list_with_default()


def test_repository_window():
    items = list(range(300))
    assert len(fetch_default_window(items)) == MAX_PAGE_SIZE
