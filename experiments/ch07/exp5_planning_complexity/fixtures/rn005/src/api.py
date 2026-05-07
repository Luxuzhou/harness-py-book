"""Pagination logic — uses direct from-import style."""
from src.constants import MAX_PAGE_SIZE


def paginate(items: list, page: int, size: int = MAX_PAGE_SIZE) -> list:
    if size > MAX_PAGE_SIZE:
        size = MAX_PAGE_SIZE
    start = page * size
    return items[start:start + size]
