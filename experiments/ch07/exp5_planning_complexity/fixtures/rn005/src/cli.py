"""CLI entry — uses aliased module import.

Note: this style is `import X as Y` then references via `Y.NAME`.
A grep for the constant name will find this; a grep that only looks at
`from ... import` lines will miss it.
"""
import src.constants as consts


def cmd_list_with_default():
    return f"using page size = {consts.MAX_PAGE_SIZE}"


def cmd_list_with_min():
    return f"min page size = {consts.MIN_PAGE_SIZE}"
