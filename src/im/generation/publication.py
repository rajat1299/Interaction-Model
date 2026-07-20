"""One complete-directory publication primitive for generated review evidence."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from tempfile import TemporaryDirectory


def publish_directory_transaction(
    target: Path,
    files: Mapping[str, bytes],
    *,
    expected_before: frozenset[str] | None = None,
    verify_staged: Callable[[Path], None] | None = None,
) -> None:
    """Publish a closed inventory atomically; ``None`` is create-only."""
    if not files:
        raise ValueError("publication files must be nonempty")
    expected = dict(files)
    for name in expected:
        _validate_relative_path(name)

    parent = target.parent.resolve()
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / target.name
    create_only = expected_before is None
    lock = parent / f".{target.name}.publication-lock"
    try:
        lock.mkdir()
    except FileExistsError:
        raise FileExistsError(f"publication already in progress: {target}") from None
    try:
        if create_only:
            if target.exists() or target.is_symlink():
                raise FileExistsError(f"publication target already exists: {target}")
        elif frozenset(directory_bytes(target)) != expected_before:
            raise ValueError("publication source inventory is not the expected transition state")
        with TemporaryDirectory(prefix=f".{target.name}-transaction-", dir=parent) as temporary:
            transaction = Path(temporary)
            staged = transaction / "staged"
            staged.mkdir()
            for name, data in expected.items():
                path = staged / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            verify_directory_bytes(staged, expected)
            if verify_staged is not None:
                verify_staged(staged)

            backup = transaction / "backup"
            failed = transaction / "failed"
            try:
                if create_only:
                    if target.exists() or target.is_symlink():
                        raise FileExistsError(f"publication target already exists: {target}")
                else:
                    target.replace(backup)
                staged.replace(target)
                verify_directory_bytes(target, expected)
                if verify_staged is not None:
                    verify_staged(target)
            except BaseException:
                if backup.exists():
                    if target.exists():
                        target.replace(failed)
                    backup.replace(target)
                elif create_only and target.exists() and not staged.exists():
                    target.replace(failed)
                raise
    finally:
        lock.rmdir()


def directory_bytes(root: Path) -> dict[str, bytes]:
    """Read one real directory whose only directories are parents of real files."""
    if root.is_symlink() or not root.is_dir():
        raise ValueError("publication directory must be a real directory")
    files: dict[str, bytes] = {}
    directories: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ValueError("publication directory must not contain symlinks")
        if path.is_dir():
            directories.add(relative)
        elif path.is_file():
            files[relative] = path.read_bytes()
        else:
            raise ValueError("publication directory contains an unsupported path")
    if directories != _parent_directories(files):
        raise ValueError("publication directory contains an unexpected directory")
    return files


def verify_directory_bytes(root: Path, expected: Mapping[str, bytes]) -> None:
    if directory_bytes(root) != dict(expected):
        raise ValueError("published directory differs from its complete staged inventory")


def _parent_directories(paths: Mapping[str, object]) -> set[str]:
    return {
        parent.as_posix() for name in paths for parent in Path(name).parents if parent != Path(".")
    }


def _validate_relative_path(value: str) -> None:
    path = Path(value)
    if path.is_absolute() or not path.parts or ".." in path.parts or path.as_posix() != value:
        raise ValueError("publication path is unsafe")
