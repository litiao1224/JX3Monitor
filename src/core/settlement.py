# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Settlement engine.

Extracts structured business events from raw chat records, computes
raid/team settlement reports, and writes settlement_report.json.

This module is the *only* place that orchestrates the full settlement
pipeline.  All parsing, auction management, identity inference, and
reconciliation logic lives in dedicated sub-modules.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.core.analysis import analyze_session
from src.core.auction import build_auction_instances, filter_relisted_auction_instances
from src.core.instance_detect import detect_instance_name
from src.core.identity_inference import (
    apply_identity_override,
    current_identity_from_jx3_path,
    identity_from_path,
    infer_identity_from_session_files,
)
from src.core.reconciliation import (
    dedupe_settlement_snapshots,
    purchase_gap_note,
    purchase_gap_status,
    purchase_gap_status_label,
    reconciliation_source_label,
)
from src.core.json_io import load_jsonl, read_json, write_json
from src.core.money import copper_to_gold, money_parts_to_copper
from src.core.timestamps import now_ts, ts_label

# Alias used by gui_ctk/dialogs.py
build_settlement_report = None  # assigned below


def extract_settlement(
    session_dir: Path,
    member_count: Optional[int] = None,
    self_name: str = "你",
    personal_subsidy_gold: Optional[float] = None,
    role_name_override: Optional[str] = None,
    current_jx3_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build a full settlement report for a session directory."""

    # ── 1. Analysis & identity ────────────────────────────────────
    business_summary = analyze_session(session_dir)
    session_info = read_json(session_dir / "session.json", read_json(session_dir / "session_meta.json", {}))
    is_html_session = session_info.get("source") == "exported_chatlog_html" or bool(session_info.get("html_path"))

    session_identity = infer_identity_from_session_files(session_dir)
    if not session_identity:
        session_identity = session_info.get("identity")
    if not session_identity and current_jx3_path:
        session_identity = current_identity_from_jx3_path(current_jx3_path)
    if not session_identity:
        for raw_ev in load_jsonl(session_dir / "raw_events.jsonl") or []:
            src = raw_ev.get("db")
            if src:
                session_identity = identity_from_path(Path(src))
                if session_identity and (session_identity.get("role_name") or session_identity.get("uid")):
                    break
    session_identity = apply_identity_override(session_identity, role_name_override)

    # ── 2. Collect business events ────────────────────────────────
    business_path = session_dir / "business_events.jsonl"
    explicit_purchases: Dict[str, Dict[str, Any]] = {}
    superseded_purchases: List[Dict[str, Any]] = []
    settlement_snapshots: List[Dict[str, Any]] = []
    auction_starts: List[Dict[str, Any]] = []
    all_bids: List[Dict[str, Any]] = []
    participants = set()
    self_money_gain_copper = 0
    boss_reward_copper = 0
    boss_reward_events: List[Dict[str, Any]] = []
    self_money_events: List[Dict[str, Any]] = []
    item_gains: List[Dict[str, Any]] = []
    team_append_incomes: List[Dict[str, Any]] = []

    for e in load_jsonl(business_path) or []:
        kind = e.get("kind")
        if kind == "final_purchase":
            item = e.get("item")
            explicit_key = f"explicit:{item}|{e.get('time')}|{e.get('rowid')}|{e.get('buyer')}|{e.get('amount_text')}"
            prev = explicit_purchases.get(explicit_key)
            if prev is None or (e.get("time") or 0, e.get("rowid") or 0) >= (prev.get("time") or 0, prev.get("rowid") or 0):
                if prev is not None:
                    superseded_purchases.append(prev)
                explicit_purchases[explicit_key] = e
            else:
                superseded_purchases.append(e)
            participants.add(e.get("buyer"))
            participants.add(e.get("target"))
            snap = e.get("settlement_snapshot")
            if snap:
                settlement_snapshots.append({**snap, "time": e.get("time"), "label": e.get("label"), "source_text": e.get("text")})
        elif kind == "settlement_summary":
            settlement_snapshots.append({
                "total_income_gold": e.get("total_income_gold"),
                "subsidy_gold": e.get("subsidy_gold"),
                "distributable_gold": e.get("distributable_gold"),
                "member_count": e.get("member_count"),
                "base_wage_gold": e.get("base_wage_gold"),
                "time": e.get("time"),
                "label": e.get("label"),
                "source_text": e.get("text"),
            })
        elif kind == "auction_start":
            auction_starts.append(e)
        elif kind == "bid":
            all_bids.append(e)
            participants.add(e.get("bidder"))
            item = e.get("item")
            prev = explicit_purchases.get(item)
            # Track highest bid per item (legacy, mostly unused now)
        elif kind == "team_message":
            if e.get("speaker"):
                participants.add(e.get("speaker"))
        elif kind == "item_gain":
            item_gains.append(e)
            player = e.get("player")
            if player and player != self_name:
                participants.add(player)
        elif kind == "money_gain":
            copper = int(e.get("amount_copper") or money_parts_to_copper(int(e.get("gold") or 0), int(e.get("silver") or 0), int(e.get("copper") or 0)))
            if copper == money_parts_to_copper(10, 0, 0):
                boss_reward_copper += copper
                boss_reward_events.append(e)
            else:
                self_money_gain_copper += copper
                self_money_events.append(e)
        elif kind == "team_append_income":
            team_append_incomes.append(e)
            if e.get("player"):
                participants.add(e.get("player"))

    # ── 3. Auction fallback ───────────────────────────────────────
    auction_instances = build_auction_instances(auction_starts, all_bids)
    relisted_instances = filter_relisted_auction_instances(auction_instances)
    fallback_purchases = {
        inst["item"]: {
            "item": inst.get("item"),
            "bidder": inst.get("highest_bid", {}).get("bidder"),
            "amount_gold": inst.get("highest_bid", {}).get("amount_gold"),
            "time": inst.get("highest_bid", {}).get("time") or inst.get("start_time"),
            "label": inst.get("highest_bid", {}).get("label") or inst.get("start_label"),
            "text": inst.get("highest_bid", {}).get("text") or inst.get("start_text"),
        }
        for inst in relisted_instances
        if inst.get("highest_bid")
    }

    # ── 4. Purchase reconciliation ────────────────────────────────
    purchase_rows: Dict[str, Dict[str, Any]] = {}
    purchase_reconciliation: List[Dict[str, Any]] = []
    latest_same_buyer_item: Dict[Tuple[str, str], Tuple[str, Dict[str, Any]]] = {}
    for key, e in explicit_purchases.items():
        amount = int(e.get("amount_gold") or 0)
        if amount <= 0:
            continue
        sig = (str(e.get("item") or ""), str(e.get("buyer") or e.get("target") or ""))
        prev = latest_same_buyer_item.get(sig)
        if prev is None or (e.get("time") or 0, e.get("rowid") or 0) >= (prev[1].get("time") or 0, prev[1].get("rowid") or 0):
            latest_same_buyer_item[sig] = (key, e)
    keep_keys = {key for key, _e in latest_same_buyer_item.values()}
    for key, e in list(explicit_purchases.items()):
        amount = int(e.get("amount_gold") or 0)
        if amount > 0 and key not in keep_keys:
            superseded_purchases.append({**e, "superseded_reason": "same_item_buyer_later_record"})
            explicit_purchases.pop(key, None)

    fallback_merge_keys = set() if explicit_purchases else {f"fallback:{item}" for item in fallback_purchases}
    for key in sorted(set(explicit_purchases) | fallback_merge_keys):
        explicit = explicit_purchases.get(key)
        explicit_item = str(explicit.get("item") or "") if explicit else ""
        fallback_item = key.split(":", 1)[1] if key.startswith("fallback:") else explicit_item
        fallback = fallback_purchases.get(fallback_item) if key.startswith("fallback:") else None
        explicit_amount = int(explicit.get("amount_gold") or 0) if explicit else None
        fallback_amount = int(fallback.get("amount_gold") or 0) if fallback else None
        if explicit and explicit_amount and explicit_amount > 0:
            chosen = {**explicit, "reconciliation_source": "explicit_final_purchase"}
        elif fallback and fallback_amount and fallback_amount > 0:
            chosen = {**fallback, "reconciliation_source": "auction_fallback_missing_or_zero_final"}
        elif explicit:
            chosen = {**explicit, "reconciliation_source": "explicit_zero_purchase"}
        elif fallback:
            chosen = {**fallback, "reconciliation_source": "auction_fallback"}
        else:
            continue
        chosen_item = chosen.get("item") or explicit_item or fallback_item
        purchase_rows[key] = {**chosen, "item": chosen_item}
        purchase_reconciliation.append({
            "item": chosen_item,
            "chosen_source": chosen.get("reconciliation_source"),
            "chosen_source_label": reconciliation_source_label(chosen.get("reconciliation_source")),
            "chosen_amount_gold": int(chosen.get("amount_gold") or 0),
            "explicit_amount_gold": explicit_amount,
            "fallback_amount_gold": fallback_amount,
            "explicit_buyer": explicit.get("buyer") if explicit else None,
            "fallback_buyer": fallback.get("bidder") if fallback else None,
        })
    purchase_source = "explicit_final_purchase" if explicit_purchases else "auction_instance_highest_bid_fallback"

    purchases = sorted(
        [
            {
                "item": bid.get("item") or item,
                "buyer": bid.get("buyer") or bid.get("bidder"),
                "target": bid.get("target"),
                "amount_gold": int(bid.get("amount_gold") or 0),
                "reconciliation_source": bid.get("reconciliation_source"),
                "reconciliation_source_label": reconciliation_source_label(bid.get("reconciliation_source")),
                "time": bid.get("time"),
                "label": bid.get("label"),
                "source_text": bid.get("text"),
            }
            for item, bid in purchase_rows.items()
        ],
        key=lambda x: (x["time"] or 0, x["item"]),
    )
    paid_purchases = [p for p in purchases if int(p.get("amount_gold") or 0) > 0]
    zero_price_records = [p for p in purchases if int(p.get("amount_gold") or 0) <= 0]

    # ── 5. Totals & snapshot dedup ────────────────────────────────
    paid_purchase_total_gold = sum(p["amount_gold"] for p in paid_purchases)
    append_income_total_gold = sum(int(e.get("amount_gold") or 0) for e in team_append_incomes)
    calculated_total_gold = paid_purchase_total_gold + append_income_total_gold
    original_settlement_snapshot_count = len(settlement_snapshots)
    settlement_snapshots = dedupe_settlement_snapshots(settlement_snapshots)
    latest_snapshot = sorted(settlement_snapshots, key=lambda x: x.get("time") or 0)[-1] if settlement_snapshots else None
    append_income_after_snapshot_gold = sum(
        int(e.get("amount_gold") or 0)
        for e in team_append_incomes
        if latest_snapshot and latest_snapshot.get("time") is not None and (e.get("time") or 0) > (latest_snapshot.get("time") or 0)
    )
    if latest_snapshot and latest_snapshot.get("total_income_gold") is not None:
        snapshot_total_gold = int(latest_snapshot.get("total_income_gold")) + append_income_after_snapshot_gold
        total_gold = max(snapshot_total_gold, calculated_total_gold)
    else:
        total_gold = calculated_total_gold
    subsidy_gold = int(latest_snapshot.get("subsidy_gold")) if latest_snapshot and latest_snapshot.get("subsidy_gold") is not None else 0
    if latest_snapshot and latest_snapshot.get("distributable_gold") is not None and total_gold == int(latest_snapshot.get("total_income_gold") or 0):
        distributable_gold = int(latest_snapshot.get("distributable_gold"))
    else:
        distributable_gold = total_gold - subsidy_gold

    buyer_totals_counter = defaultdict(int)
    for p in paid_purchases:
        buyer_totals_counter[p["buyer"]] += p["amount_gold"]
    buyer_totals = [
        {"buyer": buyer, "total_gold": total, "items": [p for p in paid_purchases if p["buyer"] == buyer]}
        for buyer, total in sorted(buyer_totals_counter.items(), key=lambda kv: (-kv[1], kv[0] or ""))
    ]

    # ── 6. Wage / income calculation ──────────────────────────────
    inferred_member_count = len({p for p in participants if p})
    snapshot_member_count = int(latest_snapshot.get("member_count")) if latest_snapshot and latest_snapshot.get("member_count") else None
    usable_snapshot_member_count = snapshot_member_count if snapshot_member_count and snapshot_member_count > 1 else None
    divisor = member_count or usable_snapshot_member_count or inferred_member_count or None
    average_wage = (int(latest_snapshot.get("base_wage_gold")) if latest_snapshot and latest_snapshot.get("base_wage_gold") and not member_count else (distributable_gold / divisor) if divisor else None)
    self_raw_money_gain_gold = copper_to_gold(self_money_gain_copper)
    base_wage_gold = float(average_wage) if average_wage is not None else None
    latest_settlement_time = latest_snapshot.get("time") if latest_snapshot else None

    wage_receipt_candidates: List[Dict[str, Any]] = []
    for ev in ([] if is_html_session else self_money_events):
        amount_copper = int(ev.get("amount_copper") or 0)
        if amount_copper <= 0:
            continue
        if latest_settlement_time is not None and (ev.get("time") or 0) < latest_settlement_time:
            continue
        amount_gold = copper_to_gold(amount_copper)
        if amount_gold == 10:
            continue
        wage_receipt_candidates.append({
            "time": ev.get("time"), "label": ev.get("label"),
            "amount_gold": round(amount_gold, 2), "amount_copper": amount_copper,
            "source_text": ev.get("text"),
        })

    chosen_wage_receipt = None
    if wage_receipt_candidates:
        if personal_subsidy_gold is not None and base_wage_gold is not None:
            expected = base_wage_gold + float(personal_subsidy_gold)
            chosen_wage_receipt = min(wage_receipt_candidates, key=lambda x: abs(float(x["amount_gold"]) - expected))
        elif base_wage_gold is not None:
            chosen_wage_receipt = min(wage_receipt_candidates, key=lambda x: (abs(float(x["amount_gold"]) - base_wage_gold), x.get("time") or 0))
        else:
            chosen_wage_receipt = sorted(wage_receipt_candidates, key=lambda x: (x.get("time") or 0, x.get("amount_copper") or 0))[0]

    detected_personal_subsidy_gold = None
    self_actual_income_gold = None
    income_source = None
    if chosen_wage_receipt:
        self_actual_income_gold = float(chosen_wage_receipt["amount_gold"])
        income_source = "post_settlement_msg_money"
        if base_wage_gold is not None:
            detected_personal_subsidy_gold = round(self_actual_income_gold - base_wage_gold, 2)
    elif base_wage_gold is not None:
        if is_html_session:
            detected_personal_subsidy_gold = 0.0
            self_actual_income_gold = base_wage_gold
            income_source = "html_base_wage_ignore_local_money"
        else:
            detected_personal_subsidy_gold = float(personal_subsidy_gold or 0)
            self_actual_income_gold = base_wage_gold + detected_personal_subsidy_gold
            income_source = "base_wage_no_money_receipt" if personal_subsidy_gold is None else "base_wage_plus_manual_subsidy"

    wage_receipt_check = None
    if base_wage_gold is not None:
        expected_income = base_wage_gold + float(personal_subsidy_gold or (detected_personal_subsidy_gold or 0))
        actual = self_actual_income_gold if self_actual_income_gold is not None else 0
        wage_receipt_check = {
            "base_wage_gold": round(base_wage_gold, 2),
            "manual_personal_subsidy_gold": personal_subsidy_gold,
            "detected_personal_subsidy_gold": detected_personal_subsidy_gold,
            "expected_income_gold": round(expected_income, 2),
            "actual_income_gold": round(actual, 2),
            "diff_gold": round(actual - expected_income, 2),
            "status": "match" if abs(actual - expected_income) <= 1 else ("over" if actual > expected_income else "under"),
            "tolerance_gold": 1,
            "chosen_receipt": chosen_wage_receipt,
            "candidate_count": len(wage_receipt_candidates),
        }

    instance_info = detect_instance_name(session_dir)

    # ── 7. Assemble report ────────────────────────────────────────
    report: Dict[str, Any] = {
        "instance_name": instance_info.get("name"),
        "instance_confidence": instance_info.get("confidence"),
        "instance_source": instance_info.get("source"),
        "instance_info": instance_info,
        "session_start_ts": session_info.get("split_start_ts") or session_info.get("start_ts") or session_info.get("created_at"),
        "session_end_ts": session_info.get("split_end_ts") or session_info.get("end_ts") or session_info.get("stop_ts"),
        "session_start_label": ts_label(float(session_info.get("split_start_ts"))) if session_info.get("split_start_ts") is not None else (session_info.get("start_label") or (ts_label(float(session_info.get("start_ts"))) if session_info.get("start_ts") is not None and not session_info.get("start_label") else None) or session_info.get("created_label")),
        "session_stop_label": ts_label(float(session_info.get("split_end_ts"))) if session_info.get("split_end_ts") is not None else (session_info.get("end_label") or session_info.get("stop_label")),
        "purchase_count": len(paid_purchases),
        "identity": session_identity,
        "all_purchase_record_count": len(purchases),
        "zero_price_record_count": len(zero_price_records),
        "purchase_source": purchase_source,
        "session_analysis_mode": "html" if is_html_session else "live_session",
        "business_kind_counts": business_summary.get("kind_counts") or {},
        "business_event_count": business_summary.get("business_event_count"),
        "purchases": paid_purchases,
        "team_append_incomes": team_append_incomes,
        "team_append_income_count": len(team_append_incomes),
        "team_append_income_total_gold": append_income_total_gold,
        "team_append_income_after_settlement_gold": append_income_after_snapshot_gold,
        "zero_price_records": zero_price_records,
        "superseded_purchase_count": len(superseded_purchases),
        "superseded_purchases": superseded_purchases,
        "paid_purchase_total_gold": paid_purchase_total_gold,
        "calculated_purchase_total_gold": calculated_total_gold,
        "purchase_reconciliation": purchase_reconciliation,
        "purchase_total_vs_settlement_diff_gold": None,
        "total_auction_gold": total_gold,
        "subsidy_gold": subsidy_gold,
        "distributable_gold": distributable_gold,
        "latest_settlement_snapshot": latest_snapshot,
        "settlement_snapshot_count_raw": original_settlement_snapshot_count,
        "settlement_snapshot_count_after_dedupe": len(settlement_snapshots),
        "ignored_single_member_settlement_count": 1 if snapshot_member_count == 1 and member_count is None else 0,
        "auction_instance_count": len(auction_instances),
        "auction_instances_after_relist_filter_count": len(relisted_instances),
        "auction_instances_after_relist_filter": relisted_instances,
        "member_count": divisor,
        "member_count_source": "manual" if member_count else ("chat_settlement_summary" if usable_snapshot_member_count else ("ignored_chat_settlement_member_count_1" if snapshot_member_count == 1 else "inferred_from_chat_bid_and_item_gain_players")),
        "inferred_participants": sorted(p for p in participants if p),
        "average_wage_gold": round(average_wage, 2) if average_wage is not None else None,
        "self_name": self_name,
        "self_raw_money_gain_gold": round(self_raw_money_gain_gold, 2),
        "self_raw_money_gain_copper": self_money_gain_copper,
        "self_money_event_count": len(self_money_events),
        "boss_reward_gold": round(copper_to_gold(boss_reward_copper), 2),
        "boss_reward_event_count": len(boss_reward_events),
        "boss_reward_events": boss_reward_events,
        "wage_receipt_check": wage_receipt_check,
        "self_income_source": income_source,
        "personal_subsidy_gold": personal_subsidy_gold,
        "detected_personal_subsidy_gold": wage_receipt_check.get("detected_personal_subsidy_gold") if wage_receipt_check else None,
        "self_estimated_wage_gold": round(float(average_wage), 2) if average_wage is not None else None,
        "self_actual_income_gold": round(self_actual_income_gold, 2) if self_actual_income_gold is not None else None,
        "self_estimated_total_gain_gold": round(self_actual_income_gold, 2) if self_actual_income_gold is not None else None,
        "buyer_totals": buyer_totals,
        "all_bid_count": len(all_bids),
        "note": "优先使用聊天中的最终购买/结算公告；没有公告时退回到最高叫价估算；团队追加收入计入拍团总收入。工资条要求总收入/补贴/可分配/人数/底薪五项完整且数值自洽。个人收入不再累加全场 MSG_MONEY；10金整的你获得视为 boss 击杀奖励并排除；优先取工资条之后的本机到账作为实际收入，没有到账记录时用底薪作为本机实际收入。",
        "updated_at": now_ts(),
        "updated_label": ts_label(),
    }
    report["purchase_total_vs_settlement_diff_gold"] = total_gold - calculated_total_gold
    report["purchase_total_vs_settlement_status"] = purchase_gap_status(report["purchase_total_vs_settlement_diff_gold"])
    report["purchase_total_vs_settlement_status_label"] = purchase_gap_status_label(report["purchase_total_vs_settlement_status"])
    report["purchase_total_vs_settlement_note"] = purchase_gap_note(report["purchase_total_vs_settlement_diff_gold"])
    write_json(session_dir / "settlement_report.json", report)
    return report


# Final assignment
build_settlement_report = extract_settlement
