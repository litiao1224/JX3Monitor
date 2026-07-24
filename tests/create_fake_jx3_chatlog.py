from __future__ import annotations

import sqlite3
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FAKE_JX3_PATH = ROOT / "tests" / "fake_jx3" / "bin" / "zhcn_hd"


def create_fake_chatlog(base_time: int | None = None) -> Path:
    if base_time is None:
        base_time = int(time.time()) + 5
    db_path = FAKE_JX3_PATH / "interface" / "my#data" / "fake_account@zhcn_hd" / "userdata" / "chat_log" / "chatlog_fake.v2.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE ChatLog (hash INTEGER, type TEXT, time INTEGER, talker TEXT, text TEXT, msg TEXT)")
    rows = [
        (1, "MSG_ROOM", base_time + 2, "测试团长·长安城", "[房间][测试团长·长安城]：[测试装备一]开始拍卖", ""),
        (2, "MSG_ROOM", base_time + 4, "测试老板·唯我独尊", "[房间][测试老板·唯我独尊]：[测试老板·唯我独尊]以[2000金]叫价[测试装备一]", ""),
        (3, "MSG_ROOM", base_time + 8, "测试老板·唯我独尊", "[房间][测试老板·唯我独尊]：[测试老板·唯我独尊]花费[2000金]购买了[测试装备一]", ""),
        (4, "MSG_ROOM", base_time + 12, "测试团长·长安城", "[房间][测试团长·长安城]：[测试装备二]开始拍卖", ""),
        (5, "MSG_ROOM", base_time + 14, "测试老板二·梦江南", "[房间][测试老板二·梦江南]：[测试老板二·梦江南]以[3000金]叫价[测试装备二]", ""),
        (6, "MSG_ROOM", base_time + 18, "测试老板二·梦江南", "[房间][测试老板二·梦江南]：[测试老板二·梦江南]花费[3000金]购买了[测试装备二]", ""),
        (7, "MSG_ROOM", base_time + 24, "测试团长·长安城", "[房间][测试团长·长安城]：拍团目前总收入为：5000金，补贴总费用：0金， 实际可用分配金额：5000金， 分配人数：5， 每人底薪：1000金。", ""),
        (8, "MSG_MONEY", base_time + 28, "", "你获得：100000。", ""),
    ]
    con.executemany("INSERT INTO ChatLog(hash, type, time, talker, text, msg) VALUES (?, ?, ?, ?, ?, ?)", rows)
    con.commit()
    con.close()
    return db_path


if __name__ == "__main__":
    path = create_fake_chatlog()
    print(path)
    print(FAKE_JX3_PATH)
