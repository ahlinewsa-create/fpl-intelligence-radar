"""Keep one human-facing GitHub Actions button for Global Hunter."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def load(path):
    # BaseLoader preserves GitHub's YAML 'on' field (PyYAML 1.1 otherwise
    # interprets it as Boolean true).
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_daily_report_is_only_manual_workflow():
    manual = [path.name for path in ROOT.glob("*.yml")
              if "workflow_dispatch" in (load(path).get("on") or {})]
    assert manual == ["daily-report.yml"]


def test_full_daily_flow_has_all_steps_in_order():
    spec = load(ROOT / "daily-report.yml")
    assert "schedule" in spec["on"]
    steps = spec["jobs"]["report"]["steps"]
    names = [step.get("name", "") for step in steps]
    required = [
        "Test",
        "Fallback collection",
        "Verify combined analysis preview (NO EMAIL)",
        "Render final daily report",
        "Persist report BEFORE sending",
        "Claim daily email if Gmail secrets exist",
        "Persist claim BEFORE SMTP call",
        "Send claimed email",
        "Persist delivery attempt",
        "Upload report backup",
    ]
    positions = [names.index(name) for name in required]
    assert positions == sorted(positions)
    preview = next(s for s in steps if s.get("name") == required[2])
    assert "python main.py dry-run" in preview["run"]
    assert preview.get("env", {}).get("HUNTER_NOTIFICATIONS_ENABLED") == "0"


def test_background_collector_remains_scheduled_but_not_manual():
    config = load(ROOT / "collect.yml")
    assert "schedule" in config["on"]
    assert "workflow_dispatch" not in config["on"]
