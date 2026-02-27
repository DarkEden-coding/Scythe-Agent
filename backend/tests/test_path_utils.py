from pathlib import Path

import pytest

from app.tools.path_utils import resolve_path, sanitize_raw_path


def test_sanitize_raw_path_trims_trailing_json_delimiter_cluster() -> None:
    raw = "/tmp/work/Shooter.java}},{"  # common malformed suffix from streamed args
    assert sanitize_raw_path(raw) == "/tmp/work/Shooter.java"


def test_sanitize_raw_path_strips_quote_brace_from_agent_noise() -> None:
    """Agent may emit path'}, path`} from markdown/code block formatting."""
    assert (
        sanitize_raw_path(
            r"E:\Ceph-Mirror\Vs-Code-Projects\Files\src\Files.App\Utils\Storage\Operations\FileOperationsHelpers.cs'}"
        )
        == r"E:\Ceph-Mirror\Vs-Code-Projects\Files\src\Files.App\Utils\Storage\Operations\FileOperationsHelpers.cs"
    )


def test_resolve_path_recovers_from_trailing_delimiter_cluster(tmp_path: Path) -> None:
    target = tmp_path / "Shooter.java"
    target.write_text("class Shooter {}", encoding="utf-8")
    raw = str(target) + "}},{"

    resolved = resolve_path(raw, project_root=str(tmp_path))

    assert resolved == target.resolve()


def test_sanitize_raw_path_keeps_single_trailing_brace_name(tmp_path: Path) -> None:
    weird_name = tmp_path / "data}"
    weird_name.write_text("ok", encoding="utf-8")

    assert sanitize_raw_path(str(weird_name)) == str(weird_name)
    assert resolve_path(str(weird_name), project_root=str(tmp_path)) == weird_name.resolve()


def test_resolve_path_still_rejects_relative_paths() -> None:
    with pytest.raises(ValueError, match="Path must be absolute"):
        resolve_path("src/main.py}},{", project_root="/tmp/project")
