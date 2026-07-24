# -*- coding: utf-8 -*-
"""Unit tests for active character chat log scanning filtering."""

import time
from pathlib import Path
import pytest
from src.core.scanner import find_chatlog_dbs, get_active_mydata_dirs, _CHATLOG_CACHE


def test_get_active_mydata_dirs(tmp_path: Path):
    zhcn_hd = tmp_path / "bin" / "zhcn_hd"
    mydata = zhcn_hd / "interface" / "my#data"
    mydata.mkdir(parents=True)

    # Create 4 role directories with different mtimes
    roles = []
    now = time.time()
    for i in range(4):
        role_dir = mydata / f"100{i}@zhcn_hd"
        chat_dir = role_dir / "userdata" / "chat_log"
        chat_dir.mkdir(parents=True)
        db_file = chat_dir / "chatlog_1.v2.db"
        db_file.write_text("fake sqlite db data")
        
        # Set mtimes: role 0 newest (now), role 3 oldest (now - 10000)
        mtime = now - (i * 3600)
        import os
        os.utime(db_file, (mtime, mtime))
        roles.append(role_dir)

    # Test top 2 active roles
    active = get_active_mydata_dirs(zhcn_hd, max_active_roles=2, active_window_hours=24.0)
    assert active is not None
    assert len(active) == 2
    assert active[0] == roles[0]
    assert active[1] == roles[1]

    # Clear cache and test find_chatlog_dbs returns DBs only for top 2 roles
    _CHATLOG_CACHE.clear()
    dbs = find_chatlog_dbs(zhcn_hd, force_full_scan=True, max_active_roles=2, active_window_hours=24.0)
    assert len(dbs) == 2
    assert dbs[0] == roles[0] / "userdata" / "chat_log" / "chatlog_1.v2.db"
    assert dbs[1] == roles[1] / "userdata" / "chat_log" / "chatlog_1.v2.db"


def test_find_chatlog_dbs_fallback_when_max_roles_zero(tmp_path: Path):
    zhcn_hd = tmp_path / "bin" / "zhcn_hd"
    mydata = zhcn_hd / "interface" / "my#data"
    
    role1 = mydata / "1001@zhcn_hd" / "userdata" / "chat_log"
    role1.mkdir(parents=True)
    db1 = role1 / "chatlog_1.v2.db"
    db1.write_text("fake db 1")

    role2 = mydata / "1002@zhcn_hd" / "userdata" / "chat_log"
    role2.mkdir(parents=True)
    db2 = role2 / "chatlog_1.v2.db"
    db2.write_text("fake db 2")

    _CHATLOG_CACHE.clear()
    # When max_active_roles=0, it should fallback to full glob scan (all 2 DBs)
    dbs = find_chatlog_dbs(zhcn_hd, force_full_scan=True, max_active_roles=0)
    assert len(dbs) == 2
