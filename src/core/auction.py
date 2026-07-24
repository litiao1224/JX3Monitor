# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Auction instance management.

Groups auction-start events with their bids, computes highest bids,
and handles re-list / relist filtering.
"""
from __future__ import annotations

from typing import Any, Dict, List


def build_auction_instances(
    starts: List[Dict[str, Any]], bids: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Group room bids under the nearest preceding auction-start event."""
    instances: List[Dict[str, Any]] = []
    for idx, s in enumerate(sorted(starts, key=lambda x: (x.get("time") or 0, x.get("rowid") or 0))):
        instances.append({
            "instance_id": f"auction_{idx + 1:04d}",
            "item": s.get("item"),
            "start_time": s.get("time"),
            "start_label": s.get("label"),
            "start_text": s.get("text"),
            "start_rowid": s.get("rowid"),
            "bids": [],
            "highest_bid": None,
        })
    for b in sorted(bids, key=lambda x: (x.get("time") or 0, x.get("rowid") or 0)):
        item = b.get("item")
        bt = b.get("time") or 0
        candidates = [i for i in instances if i.get("item") == item and (i.get("start_time") or 0) <= bt]
        if not candidates:
            instances.append({
                "instance_id": f"orphan_bid_{len(instances) + 1:04d}",
                "item": item,
                "start_time": None,
                "start_label": None,
                "start_text": None,
                "start_rowid": None,
                "bids": [b],
                "highest_bid": {
                    "bidder": b.get("bidder"),
                    "amount_gold": int(b.get("amount_gold") or 0),
                    "time": b.get("time"),
                    "label": b.get("label"),
                    "text": b.get("text"),
                },
            })
            continue
        inst = candidates[-1]
        inst["bids"].append(b)
        hb = inst.get("highest_bid")
        amount = int(b.get("amount_gold") or 0)
        if hb is None or amount > int(hb.get("amount_gold") or 0):
            inst["highest_bid"] = {
                "bidder": b.get("bidder"),
                "amount_gold": amount,
                "time": b.get("time"),
                "label": b.get("label"),
                "text": b.get("text"),
            }
    return instances


def filter_relisted_auction_instances(instances: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep the latest sold instance for each item name."""
    latest_by_item: Dict[str, Dict[str, Any]] = {}
    for inst in sorted(instances, key=lambda x: (x.get("start_time") or 0, x.get("start_rowid") or 0)):
        item = inst.get("item")
        if not item or not inst.get("highest_bid"):
            continue
        latest_by_item[item] = inst
    return sorted(latest_by_item.values(), key=lambda x: (x.get("start_time") or 0, x.get("item") or ""))
