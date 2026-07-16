"""Path resolution helpers for cwd-scoped agent tools."""

from __future__ import annotations

from pathlib import Path


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def candidate_paths(
    cwd: Path,
    raw_path: str | Path,
    extra_roots: list[str | Path] | None = None,
) -> list[Path]:
    raw = str(raw_path)
    path = Path(raw)
    cwd = cwd.resolve()
    roots = [cwd]
    for root in extra_roots or []:
        root_path = Path(root)
        roots.append((cwd / root_path).resolve() if not root_path.is_absolute() else root_path.resolve())

    candidates: list[Path] = []
    if path.is_absolute():
        candidates.append(path.resolve())
    else:
        candidates.append((cwd / path).resolve())
        parts = [p for p in path.parts if p not in ('', '.')]

        for root in roots:
            if root.name in parts:
                idx = parts.index(root.name)
                if idx < len(parts) - 1:
                    candidates.append((root / Path(*parts[idx + 1:])).resolve())
            candidates.append((root / path).resolve())

        for ancestor in cwd.parents:
            candidates.append((ancestor / path).resolve())

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def resolve_agent_path(
    cwd: Path,
    raw_path: str | Path,
    *,
    allowed_roots: list[str | Path] | None = None,
    must_exist: bool = False,
) -> Path:
    roots = [cwd.resolve()]
    for root in allowed_roots or []:
        root_path = Path(root)
        roots.append((cwd / root_path).resolve() if not root_path.is_absolute() else root_path.resolve())

    fallback: Path | None = None
    for candidate in candidate_paths(cwd, raw_path, roots):
        if not any(is_relative_to(candidate, root) for root in roots):
            continue
        if fallback is None:
            fallback = candidate
        if candidate.exists():
            return candidate
        if not must_exist and candidate.parent.exists():
            return candidate

    if fallback is not None and not must_exist:
        return fallback
    return candidate_paths(cwd, raw_path, roots)[0]
