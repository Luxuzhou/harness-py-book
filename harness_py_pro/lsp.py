"""
代码智能（基于AST）
==================
提供Python代码的结构化分析：符号查找、引用搜索、文档提取。
不依赖外部LSP Server，直接用Python的ast模块。

对标OpenHarness services/lsp，但专注Python且零外部依赖。

核心能力：
  1. index()         — 扫描项目所有.py文件，构建符号表
  2. find_symbol()   — 精确查找符号定义（类/函数/方法）
  3. find_references() — 在AST Name节点中搜索符号引用
  4. file_outline()  — 文件符号大纲（类似IDE的Outline View）
  5. get_docstring()  — 提取指定符号的docstring
  6. search_symbols() — 模糊搜索符号名

典型用法::

    ci = CodeIntelligence(Path('/path/to/project'))
    ci.index()
    symbols = ci.find_symbol('TokenBudget')
    refs = ci.find_references('estimate_tokens')
    outline = ci.file_outline('agent.py')
    doc = ci.get_docstring('Compressor.compress')
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# 符号数据模型
# ---------------------------------------------------------------------------

@dataclass
class Symbol:
    """代码符号（类/函数/方法/变量）。

    Attributes:
        name:      符号名。
        kind:      符号类型: 'class' | 'function' | 'method' | 'variable'。
        file:      所在文件（相对于项目根目录）。
        line:      定义所在行号。
        docstring: 文档字符串（如果有）。
        parent:    父符号名（方法的父类名），顶层符号为空。
    """

    name: str
    kind: str
    file: str
    line: int
    docstring: str = ''
    parent: str = ''

    @property
    def qualified_name(self) -> str:
        """带限定的名称，如 ``ClassName.method_name``。"""
        if self.parent:
            return f'{self.parent}.{self.name}'
        return self.name


# ---------------------------------------------------------------------------
# 代码智能分析器
# ---------------------------------------------------------------------------

class CodeIntelligence:
    """Python代码智能分析器。

    基于标准库 ``ast`` 模块，不需要任何外部依赖。
    索引后在内存中维护符号表，支持查找、引用搜索和大纲生成。

    Usage::

        ci = CodeIntelligence(project_root)
        ci.index()
        symbols = ci.find_symbol('TokenBudget')
        refs = ci.find_references('estimate_tokens')
        outline = ci.file_outline('agent.py')
        doc = ci.get_docstring('Compressor.compress')
    """

    def __init__(self, project_root: Path):
        self._root = Path(project_root)
        # name -> [Symbol, ...] （同名可能多个定义）
        self._symbols: dict[str, list[Symbol]] = {}
        # relative_path -> ast.Module
        self._files: dict[str, ast.Module] = {}
        # relative_path -> source text（用于引用搜索时行号映射）
        self._sources: dict[str, str] = {}

    # -- 索引 -----------------------------------------------------------------

    def index(self, glob_pattern: str = '**/*.py'):
        """索引项目中的所有Python文件。

        Args:
            glob_pattern: 文件匹配模式，默认索引所有 ``.py`` 文件。
        """
        self._symbols.clear()
        self._files.clear()
        self._sources.clear()

        for py_file in sorted(self._root.glob(glob_pattern)):
            # 跳过常见的非项目目录
            rel = py_file.relative_to(self._root)
            rel_str = str(rel).replace('\\', '/')
            parts = rel.parts
            if any(p.startswith('.') or p == '__pycache__' for p in parts):
                continue

            try:
                source = py_file.read_text(encoding='utf-8', errors='replace')
                tree = ast.parse(source, filename=rel_str)
            except (SyntaxError, OSError):
                continue

            self._files[rel_str] = tree
            self._sources[rel_str] = source
            self._extract_symbols(tree, rel_str)

    def _extract_symbols(self, tree: ast.Module, filepath: str):
        """从AST中提取所有符号定义。"""
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                sym = Symbol(
                    name=node.name,
                    kind='class',
                    file=filepath,
                    line=node.lineno,
                    docstring=ast.get_docstring(node) or '',
                )
                self._register(sym)
                # 提取类内方法
                for item in ast.iter_child_nodes(node):
                    if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                        method_sym = Symbol(
                            name=item.name,
                            kind='method',
                            file=filepath,
                            line=item.lineno,
                            docstring=ast.get_docstring(item) or '',
                            parent=node.name,
                        )
                        self._register(method_sym)

            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                sym = Symbol(
                    name=node.name,
                    kind='function',
                    file=filepath,
                    line=node.lineno,
                    docstring=ast.get_docstring(node) or '',
                )
                self._register(sym)

            elif isinstance(node, ast.Assign):
                # 模块级变量赋值
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        sym = Symbol(
                            name=target.id,
                            kind='variable',
                            file=filepath,
                            line=node.lineno,
                        )
                        self._register(sym)

    def _register(self, sym: Symbol):
        """注册符号到索引。"""
        self._symbols.setdefault(sym.name, []).append(sym)

    # -- 查找定义 --------------------------------------------------------------

    def find_symbol(self, name: str) -> list[Symbol]:
        """查找符号定义（精确匹配名称）。

        Args:
            name: 符号名。支持简单名（如 ``TokenBudget``）
                  或限定名（如 ``Compressor.compress``）。

        Returns:
            匹配的符号列表（可能多个同名定义）。
        """
        # 尝试限定名匹配
        if '.' in name:
            parent, child = name.rsplit('.', 1)
            results = []
            for sym in self._symbols.get(child, []):
                if sym.parent == parent:
                    results.append(sym)
            return results

        return list(self._symbols.get(name, []))

    # -- 查找引用 --------------------------------------------------------------

    def find_references(self, name: str) -> list[tuple[str, int]]:
        """查找符号的引用位置（在AST的Name节点中搜索）。

        Args:
            name: 符号名（不支持限定名）。

        Returns:
            ``[(file, line), ...]`` 列表，按文件名和行号排序。
        """
        refs: list[tuple[str, int]] = []

        for filepath, tree in self._files.items():
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id == name:
                    refs.append((filepath, node.lineno))
                elif isinstance(node, ast.Attribute) and node.attr == name:
                    refs.append((filepath, node.lineno))

        refs.sort()
        return refs

    # -- 文件大纲 --------------------------------------------------------------

    def file_outline(self, filepath: str) -> list[Symbol]:
        """获取文件的符号大纲（类似IDE的Outline View）。

        Args:
            filepath: 文件路径（相对于项目根目录）。

        Returns:
            该文件中的所有符号，按行号排序。
        """
        # 规范化路径分隔符
        filepath = filepath.replace('\\', '/')

        # 支持传入绝对路径或仅文件名
        matched_key: Optional[str] = None
        if filepath in self._files:
            matched_key = filepath
        else:
            for key in self._files:
                if key.endswith(filepath) or key.endswith('/' + filepath):
                    matched_key = key
                    break

        if matched_key is None:
            return []

        result: list[Symbol] = []
        for syms in self._symbols.values():
            for sym in syms:
                if sym.file == matched_key:
                    result.append(sym)

        result.sort(key=lambda s: s.line)
        return result

    # -- 获取Docstring ---------------------------------------------------------

    def get_docstring(self, qualified_name: str) -> str:
        """获取指定符号的docstring。

        Args:
            qualified_name: 符号名或限定名（如 ``Compressor.compress``）。

        Returns:
            docstring文本，未找到则返回空字符串。
        """
        symbols = self.find_symbol(qualified_name)
        if symbols:
            return symbols[0].docstring
        return ''

    # -- 模糊搜索 --------------------------------------------------------------

    def search_symbols(self, query: str) -> list[Symbol]:
        """模糊搜索符号名（大小写不敏感的子串匹配）。

        Args:
            query: 搜索关键词。

        Returns:
            匹配的符号列表，按名称字母序排序。
        """
        query_lower = query.lower()
        results: list[Symbol] = []
        for name, syms in self._symbols.items():
            if query_lower in name.lower():
                results.extend(syms)
        results.sort(key=lambda s: (s.name.lower(), s.file, s.line))
        return results

    # -- 统计信息 --------------------------------------------------------------

    @property
    def indexed_files(self) -> int:
        """已索引的文件数。"""
        return len(self._files)

    @property
    def total_symbols(self) -> int:
        """索引中的总符号数。"""
        return sum(len(syms) for syms in self._symbols.values())

    def summary(self) -> dict:
        """返回索引摘要信息。"""
        kind_counts: dict[str, int] = {}
        for syms in self._symbols.values():
            for sym in syms:
                kind_counts[sym.kind] = kind_counts.get(sym.kind, 0) + 1
        return {
            'files': self.indexed_files,
            'symbols': self.total_symbols,
            'by_kind': kind_counts,
        }
