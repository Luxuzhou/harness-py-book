"""
Subject 示例：Tool Description（复用 Ch4 的 V1/V2 描述）。

直接桥接 experiments/ch04/exp1_tool_description_eval/descriptions.py，
证明 Ch4 的工作可以无缝接入 Ch8 的通用框架。
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE.parent.parent.parent / 'ch04' / 'exp1_tool_description_eval'))

from framework import Subject  # noqa: E402

try:
    from descriptions import V1_DESCRIPTIONS, V2_DESCRIPTIONS, apply_descriptions  # noqa: E402
    _HAS_CH4 = True
except ImportError as e:
    _HAS_CH4 = False
    _IMPORT_ERR = str(e)


class ToolDescriptionSubject(Subject):
    """
    apply() 时调用 Ch4 的 apply_descriptions() 修改 ToolRegistry 中工具描述。
    revert() 时调用 apply_descriptions('v1') 还原（默认基线）。
    """

    def apply(self) -> None:
        if not _HAS_CH4:
            raise RuntimeError(
                f"无法导入 Ch4 描述模块：{_IMPORT_ERR}。"
                f"确认 experiments/ch04/exp1_tool_description_eval/descriptions.py 存在。"
            )
        if self.version not in ('v1', 'v2'):
            raise ValueError(f"Unknown version: {self.version}")
        # apply_descriptions(registry, version) 接 ToolRegistry 实例。Ch8 框架
        # 在 _build_capture_registry 时 monkey-patch create_default_registry，
        # 让新建 registry 时自动套用本 subject 的版本描述。
        from harness_py_pro import tools as _tools_mod
        self._saved_state = _tools_mod.create_default_registry
        version = self.version

        def _patched_default_registry():
            reg = self._saved_state()
            apply_descriptions(reg, version)
            return reg

        _tools_mod.create_default_registry = _patched_default_registry
        # framework 在自身命名空间也 import 了 create_default_registry，需同步替换
        import framework as _fw
        _fw.create_default_registry = _patched_default_registry

        descs = V1_DESCRIPTIONS if self.version == 'v1' else V2_DESCRIPTIONS
        self.description = f"tool_description {self.version}: {len(descs)} tools"

    def revert(self) -> None:
        if self._saved_state is not None:
            from harness_py_pro import tools as _tools_mod
            _tools_mod.create_default_registry = self._saved_state
            import framework as _fw
            _fw.create_default_registry = self._saved_state
            self._saved_state = None
