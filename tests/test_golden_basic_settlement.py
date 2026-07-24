from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jx3_click_monitor as core

FIXTURE_DIR = ROOT / "tests" / "golden"
WORK_DIR = FIXTURE_DIR / "_work" / "basic_settlement"
RAW_EVENTS = FIXTURE_DIR / "basic_settlement.raw_events.jsonl"
EXPECTED = FIXTURE_DIR / "basic_settlement.expected.json"


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def prepare_session() -> None:
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    WORK_DIR.mkdir(parents=True)
    shutil.copyfile(RAW_EVENTS, WORK_DIR / "raw_events.jsonl")
    core.write_json(
        WORK_DIR / "session.json",
        {
            "id": "golden_basic_settlement",
            "source": "golden_test",
            "status": "imported",
            "history_confirmed": False,
            "start_ts": 1781232000,
            "end_ts": 1781232060,
            "identity": {"role_name": "团长", "server": "测试服", "display": "测试服/团长"},
        },
    )


def assert_subset(actual: dict, expected: dict, path: str = "report") -> None:
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        current_path = f"{path}.{key}"
        if isinstance(expected_value, dict):
            if not isinstance(actual_value, dict):
                raise AssertionError(f"{current_path}: expected dict, got {type(actual_value).__name__}")
            assert_subset(actual_value, expected_value, current_path)
        else:
            if actual_value != expected_value:
                raise AssertionError(f"{current_path}: expected {expected_value!r}, got {actual_value!r}")


def main() -> int:
    prepare_session()
    business_summary = core.analyze_session(WORK_DIR)
    report = core.extract_settlement(WORK_DIR, self_name="团长")
    expected = json.loads(EXPECTED.read_text(encoding="utf-8-sig"))

    business_events = load_jsonl(WORK_DIR / "business_events.jsonl")
    assert business_summary["business_event_count"] == expected["business_event_count"]
    assert business_summary["kind_counts"] == expected["kind_counts"]
    assert [event["kind"] for event in business_events] == expected["business_kinds"]
    assert_subset(report, expected["report_subset"])

    print("golden basic_settlement passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
