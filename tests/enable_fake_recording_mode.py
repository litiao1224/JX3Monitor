from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.create_fake_jx3_chatlog import FAKE_JX3_PATH, create_fake_chatlog
CONFIG_PATH = ROOT / "gui_config.json"
FAKE_OUT_DIR = ROOT / "runs" / "fake_live"


def main() -> None:
    chatlog = create_fake_chatlog()
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig")) if CONFIG_PATH.exists() else {}
    except Exception:
        config = {}
    config["jx3_path"] = str(FAKE_JX3_PATH)
    config["out_dir"] = str(FAKE_OUT_DIR)
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成假聊天库：{chatlog}")
    print(f"已把软件配置切到假剑三路径：{FAKE_JX3_PATH}")
    print(f"测试输出目录：{FAKE_OUT_DIR}")


if __name__ == "__main__":
    main()
