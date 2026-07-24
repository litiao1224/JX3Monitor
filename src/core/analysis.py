# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Session analysis.

Analyzes raw events into business events and produces auction summaries.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from src.core.auction import build_auction_instances, filter_relisted_auction_instances
from src.core.business_events import dedupe_events_by_time_channel_text, parse_business_event
from src.core.json_io import append_jsonl, load_jsonl, write_json
from src.core.timestamps import now_ts, ts_label


def analyze_session(session_dir: Path) -> Dict[str, Any]:
    """Parse raw events into business events and produce an auction summary."""
    raw_path = session_dir / "raw_events.jsonl"
    business_path = session_dir / "business_events.jsonl"
    parsed_events: List[Dict[str, Any]] = []
    for e in load_jsonl(raw_path) or []:
        be = parse_business_event(e)
        if be:
            parsed_events.append(be)
    events = dedupe_events_by_time_channel_text(parsed_events)
    if business_path.exists():
        business_path.unlink()
    append_jsonl(business_path, events)

    kind_counts = Counter(e.get("kind") for e in events)
    auctions: Dict[str, Dict[str, Any]] = {}
    for e in events:
        if e.get("kind") == "auction_start":
            key = e["item"]
            auctions.setdefault(key, {"item": key, "starts": [], "bids": [], "highest_bid": None})
            auctions[key]["starts"].append(e)
        elif e.get("kind") == "bid":
            key = e["item"]
            auctions.setdefault(key, {"item": key, "starts": [], "bids": [], "highest_bid": None})
            auctions[key]["bids"].append(e)
            hb = auctions[key].get("highest_bid")
            if hb is None or e.get("amount_gold", 0) > hb.get("amount_gold", 0):
                auctions[key]["highest_bid"] = {
                    "bidder": e.get("bidder"),
                    "amount_gold": e.get("amount_gold"),
                    "time": e.get("time"),
                    "label": e.get("label"),
                }

    item_gains = Counter()
    money_total = 0
    team_bid_candidates = []
    for e in events:
        if e.get("kind") == "item_gain":
            item_gains[e.get("item")] += int(e.get("count") or 1)
        elif e.get("kind") == "money_gain":
            money_total += int(e.get("gold") or 0)
        elif e.get("kind") == "team_message" and e.get("bid_candidate"):
            team_bid_candidates.append(e)

    auction_list = sorted(auctions.values(), key=lambda x: (x["starts"][0].get("time") if x["starts"] else 10**18, x["item"]))
    summary = {
        "business_event_count": len(events),
        "kind_counts": dict(kind_counts.most_common()),
        "auction_item_count": len(auction_list),
        "bid_count": kind_counts.get("bid", 0),
        "money_gain_total_raw": money_total,
        "item_gain_totals_top": dict(item_gains.most_common(50)),
        "team_bid_candidate_count": len(team_bid_candidates),
        "team_bid_candidates_sample": team_bid_candidates[:30],
        "auctions": auction_list,
        "updated_at": now_ts(),
        "updated_label": ts_label(),
    }
    write_json(session_dir / "auction_summary.json", summary)
    return summary
