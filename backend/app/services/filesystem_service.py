import os
import subprocess
from pathlib import Path

from app.schemas.filesystem import FsChildOut, FsChildrenResponse


class FilesystemService:
    def __init__(self) -> None:
        self.allowed_roots = [Path("/").resolve()]
        self.restrict_to_roots = False

    def _is_within_allowed_roots(self, path: Path) -> bool:
        if not self.restrict_to_roots:
            return True
        resolved = path.resolve()
        real = Path(os.path.realpath(str(path)))
        for root in self.allowed_roots:
            try:
                resolved.relative_to(root)
                real.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def _resolve_input(self, raw_path: str | None) -> Path:
        if raw_path is None or raw_path.strip() == "":
            return self.allowed_roots[0]
        if raw_path == "~":
            target = Path.home().resolve()
        else:
            target = Path(raw_path).expanduser().resolve()
        return target

    def get_children(self, raw_path: str | None) -> FsChildrenResponse:
        target = self._resolve_input(raw_path)
        if not self._is_within_allowed_roots(target):
            raise ValueError(f"Path is outside allowed roots: {target}")
        if not target.exists() or not target.is_dir():
            raise ValueError(f"Directory not found: {target}")

        children: list[FsChildOut] = []
        try:
            entries = list(target.iterdir())
        except PermissionError:
            entries = []

        entries.sort(key=lambda item: (not item.is_dir(), item.name.lower()))
        for entry in entries:
            has_children = False
            if entry.is_dir():
                try:
                    has_children = any(entry.iterdir())
                except PermissionError:
                    has_children = False
            children.append(
                FsChildOut(
                    name=entry.name,
                    path=str(entry.resolve()),
                    kind="directory" if entry.is_dir() else "file",
                    hasChildren=has_children,
                )
            )

        parent = target.parent.resolve() if target.parent != target else None
        if parent is not None and self.restrict_to_roots and not self._is_within_allowed_roots(parent):
            parent = None

        return FsChildrenResponse(
            path=str(target),
            parentPath=str(parent) if parent is not None else None,
            children=children,
            allowedRoots=[str(root) for root in self.allowed_roots],
        )

    def pick_directory(self) -> tuple[str | None, bool]:
        script = 'try\nPOSIX path of (choose folder with prompt "Select a project folder")\non error number -128\nreturn "__CANCELLED__"\nend try'
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip() or "Failed to open native folder picker"
            raise RuntimeError(stderr)

        output = result.stdout.strip()
        if output == "__CANCELLED__":
            return (None, True)

        if not output:
            raise RuntimeError("Native folder picker did not return a path")

        target = Path(output).expanduser().resolve()
        if not target.exists() or not target.is_dir():
            raise ValueError(f"Directory not found: {target}")

        return (str(target), False)
