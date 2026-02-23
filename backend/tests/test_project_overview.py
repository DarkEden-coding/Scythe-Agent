from pathlib import Path

from app.initial_information.project_overview import add_project_overview_3_levels


def _seed_project_tree(root: Path) -> None:
    (root / "level1" / "level2" / "level3").mkdir(parents=True)
    (root / "root.txt").write_text("root", encoding="utf-8")
    (root / "level1" / "l1.txt").write_text("l1", encoding="utf-8")
    (root / "level1" / "level2" / "l2.txt").write_text("l2", encoding="utf-8")
    (root / "level1" / "level2" / "level3" / "deep.txt").write_text("deep", encoding="utf-8")


def test_project_overview_uses_max_depth_when_under_token_target(tmp_path: Path) -> None:
    _seed_project_tree(tmp_path)
    messages = [
        {"role": "system", "content": "base system"},
        {"role": "user", "content": "hello"},
    ]

    out = add_project_overview_3_levels(
        messages,
        project_path=str(tmp_path),
        max_depth=3,
        token_target=10**9,
    )

    assert out[1]["role"] == "system"
    overview = out[1]["content"]
    assert "selected depth: 3/3" in overview
    assert "level3/" in overview
    assert "{root_str}" not in overview


def test_project_overview_stops_at_first_depth_over_token_target(tmp_path: Path) -> None:
    _seed_project_tree(tmp_path)
    messages = [{"role": "user", "content": "hello"}]

    out = add_project_overview_3_levels(
        messages,
        project_path=str(tmp_path),
        max_depth=3,
        token_target=1,
    )

    overview = out[0]["content"]
    assert "selected depth: 1/3" in overview
    assert "level1/" in overview
    assert "level2/" not in overview
