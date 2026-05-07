"""Repository layer — uses package-level import.

Yet another import style. The reference is `constants.NAME`.
"""
from src import constants


def fetch_default_window(items: list) -> list:
    return items[:constants.MAX_PAGE_SIZE]


def fetch_min_window(items: list) -> list:
    return items[:constants.MIN_PAGE_SIZE]
