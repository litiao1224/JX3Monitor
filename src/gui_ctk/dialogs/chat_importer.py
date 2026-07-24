# -*- coding: utf-8 -*-
"""Chat HTML importer dialog for JX3 Click Monitor."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk
from tkinter import filedialog, messagebox

if TYPE_CHECKING:
    from jx3_click_monitor_gui_ctk import App

import jx3_click_monitor as core
from src.config import INCOME_MEMORY_PATH
from src.gui_ctk.dialogs.shared import C, F, position_dialog
from src.gui_ctk.widgets import CTkTable

logger = logging.getLogger("jx3_monitor.dialogs.chat_importer")


class ChatImporter(ctk.CTkToplevel):
    """Import chat HTML files from JX3 exports."""

    def __init__(self, app: App, parent: ctk.CTkBaseClass | None = None) -> None:
        super().__init__(parent or app)
        self.app = app
        self.title("手动导入")
        position_dialog(self, app, 1240, 820, 900, 600)
        self.transient(parent or app)
        self.grab_set()

        self._html_sessions: list[dict] = []
        self._split_sessions: list[dict] = []

        self._build_ui()

    def _build_ui(self) -> None:
        import_box = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=8,
                                  border_width=1, border_color=C["border_light"])
        import_box.pack(fill="both", expand=True, padx=8, pady=8)

        import_actions = ctk.CTkFrame(import_box, fg_color="transparent")
        import_actions.pack(fill="x", padx=10, pady=8)

        self.import_status = ctk.StringVar(
            value="可一次选择多个茗伊聊天 HTML。导入后不会自动分割，也不会进入历史记录。")
        ctk.CTkButton(import_actions, text="导入 HTML", command=self._import_files,
                      font=F["button"], fg_color=C["primary"], text_color=C["text_on_primary"],
                      hover_color=C["primary_hover"], corner_radius=6, border_width=0).pack(side="left", padx=4)
        ctk.CTkButton(import_actions, text="清空列表", command=self._clear_html_list,
                      font=F["button"], fg_color=C["toolbar_bg"], text_color=C["text_secondary"],
                      hover_color=C["toolbar_hover"], corner_radius=6, border_width=0).pack(side="left", padx=4)
        ctk.CTkLabel(import_actions, textvariable=self.import_status,
                     text_color=C["text_muted"], font=F["small"]).pack(side="left", padx=12)

        import_table_frame = ctk.CTkFrame(import_box, fg_color=C["card"], corner_radius=4)
        import_table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.html_tree = CTkTable(
            import_table_frame,
            columns=[
                {"name": "idx", "text": "序号", "width": 60, "anchor": "e"},
                {"name": "server", "text": "区服", "width": 140, "anchor": "w"},
                {"name": "role", "text": "角色", "width": 160, "anchor": "w"},
                {"name": "name", "text": "HTML名称", "width": 620, "anchor": "w"},
                {"name": "events", "text": "记录数", "width": 80, "anchor": "e"},
            ],
            row_height=28, select_mode="browse",
        )
        self.html_tree.set_theme_colors(
            bg_header=C["table_header"], fg_header=C["table_header_text"],
            bg_row_even=C["card"], bg_row_odd=C["table_alt"],
            bg_selected=C["table_selected"], fg_selected=C["table_selected_text"],
            fg_normal=C["text_primary"],
        )
        self.html_tree.pack(fill="both", expand=True)

        # ── Split sessions ──
        split_box = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=8,
                                 border_width=1, border_color=C["border_light"])
        split_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        split_actions = ctk.CTkFrame(split_box, fg_color="transparent")
        split_actions.pack(fill="x", padx=10, pady=8)

        self.selected_status_var = ctk.StringVar(
            value="选中 0 个 Session；生成结算只处理当前一条，批量结算会把选中 Session 全部纳入历史记录和收入统计。")

        for txt, cmd in [
            ("分割 Session", self._split_selected),
            ("导入 Session", self._import_session),
            ("生成结算", self._generate_selected),
            ("批量结算", self._batch_generate),
        ]:
            ctk.CTkButton(split_actions, text=txt, command=cmd, font=F["button"],
                          fg_color=C["toolbar_bg"], text_color=C["text_secondary"],
                          hover_color=C["toolbar_hover"], corner_radius=6,
                          border_width=0).pack(side="left", padx=4)
        ctk.CTkLabel(split_actions, textvariable=self.selected_status_var,
                     text_color=C["text_muted"], font=F["small"]).pack(side="left", padx=12)

        self.split_tree = CTkTable(
            split_box,
            columns=[
                {"name": "idx", "text": "序号", "width": 50, "anchor": "e"},
                {"name": "start", "text": "开始时间", "width": 150, "anchor": "w"},
                {"name": "end", "text": "结束时间", "width": 150, "anchor": "w"},
                {"name": "settlement", "text": "总金团", "width": 80, "anchor": "e"},
                {"name": "wage", "text": "底薪", "width": 65, "anchor": "e"},
                {"name": "self_income", "text": "实际收入", "width": 80, "anchor": "e"},
                {"name": "purchases", "text": "成交", "width": 60, "anchor": "e"},
                {"name": "purchase_gold", "text": "成交合计", "width": 80, "anchor": "e"},
                {"name": "duration", "text": "分钟", "width": 55, "anchor": "e"},
                {"name": "events", "text": "记录数", "width": 60, "anchor": "e"},
                {"name": "session", "text": "Session", "width": 280, "anchor": "w"},
            ],
            row_height=26, select_mode="extended",
        )
        self.split_tree.set_theme_colors(
            bg_header=C["table_header"], fg_header=C["table_header_text"],
            bg_row_even=C["card"], bg_row_odd=C["table_alt"],
            bg_selected=C["table_selected"], fg_selected=C["table_selected_text"],
            fg_normal=C["text_primary"],
        )
        self.split_tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    # ── Import methods ──

    def _import_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="选择茗伊聊天 HTML 文件",
            filetypes=[("HTML 文件", "*.html;*.htm"), ("所有文件", "*.*")],
        )
        if not paths:
            return
        count = 0
        for path in map(Path, paths):
            if not path.exists():
                continue
            try:
                msgs = core.load_exported_chatlog_messages(path)
                identity = core.identity_from_path(path) or {}
                s = {
                    "html_path": str(path),
                    "html_name": path.name,
                    "server": identity.get("server") or "",
                    "role": identity.get("role_name") or "",
                    "events": len(msgs),
                    "idx": len(self._html_sessions) + 1,
                }
                self._html_sessions.append(s)
                count += 1
            except Exception as exc:
                self.import_status.set(f"导入失败: {exc}")
                continue
        self._refresh_html_tree()
        self.import_status.set(f"已导入 {len(paths)} 个文件，{count} 个 Session。在下方分割后进入历史记录。")

    def _clear_html_list(self) -> None:
        self._html_sessions.clear()
        self.html_tree.delete_all()

    def _refresh_html_tree(self) -> None:
        self.html_tree.delete_all()
        for s in self._html_sessions:
            events = s.get("events") or s.get("event_count") or 0
            self.html_tree.insert(values=(
                s.get("idx"), s.get("server", ""), s.get("role", ""),
                s.get("html_name", ""), events,
            ), iid=str(s.get("idx")))

    def _split_selected(self) -> None:
        sel = self.html_tree.get_selection()
        if not sel:
            messagebox.showinfo("提示", "请先在 HTML 列表中选择一条记录")
            return
        idx = int(sel[0])
        html_item = next((s for s in self._html_sessions if s.get("idx") == idx), None)
        if not html_item:
            return

        out_dir = Path(self.app.out_var.get())
        html_path = Path(html_item.get("html_path", ""))
        try:
            session_dir = core.import_chatlog_html_session(html_path, out_dir)
            report = core.read_json(session_dir / "settlement_report.json", {})
            seg = {
                "session_dir": str(session_dir),
                "instance": report.get("instance_name") or "未识别剧本",
                "income": report.get("self_actual_income_gold") or 0,
                "expense": 0,
                "net": report.get("self_actual_income_gold") or 0,
                "row_iid": len(self._split_sessions) + 1,
                "idx": len(self._split_sessions) + 1,
                "confirmed": False,
                "report": report,
            }
            self._split_sessions.append(seg)
        except Exception as exc:
            messagebox.showerror("分割失败", str(exc))
            return
        self._refresh_split_table()
        messagebox.showinfo("分割完成", f"已分割为 {len(segments)} 个 Session。")

    def _refresh_split_table(self) -> None:
        self.split_tree.delete_all()
        visible_no = 0
        for item in self._split_sessions:
            visible_no += 1
            seg = item.get("segment") or {}
            report = item.get("report") or {}
            sd = Path(item.get("session_dir", ""))
            self.split_tree.insert(values=(
                visible_no, seg.get("start_label"), seg.get("end_label"),
                report.get("total_auction_gold"), report.get("average_wage_gold"),
                f"{report.get('self_actual_income_gold') or 0} 金",
                report.get("purchase_count"), report.get("calculated_purchase_total_gold"),
                seg.get("duration_minutes"), seg.get("event_count"),
                ("已加入 · " if item.get("confirmed") else "") + sd.name,
            ), iid=str(item.get("row_iid") or item.get("idx")))

    def _import_session(self) -> None:
        folder = filedialog.askdirectory(title="选择 Session 目录")
        if not folder:
            return
        source = Path(folder)
        try:
            session_dir = self._copy_local_session_dir(source)
            report = self._safe_build_session_report(session_dir)
        except Exception as exc:
            messagebox.showerror("错误", str(exc))
            return

        item = {
            "row_iid": len(self._split_sessions) + 1,
            "idx": len(self._split_sessions) + 1,
            "session_dir": str(session_dir),
            "segment": self._session_segment_from_dir(session_dir),
            "report": report or {},
            "confirmed": False,
        }
        self._split_sessions.append(item)
        self._refresh_split_table()
        if hasattr(self.app, "refresh_history_sessions"):
            self.app.refresh_history_sessions()
        messagebox.showinfo("成功", f"已导入 Session: {session_dir.name}")

    def _copy_local_session_dir(self, source: Path) -> Path:
        if not source.exists() or not source.is_dir():
            raise ValueError("请选择一个有效的 Session 目录")
        if not self._looks_like_session_dir(source):
            raise ValueError("该目录看起来不像一个有效的 Session 目录")
        out_dir = Path(self.app.out_var.get())
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            if source.resolve().is_relative_to(out_dir.resolve()):
                return source
        except Exception:
            pass
        target = out_dir / source.name
        if target.exists():
            base = target.name
            for n in range(2, 1000):
                candidate = out_dir / f"{base}_{n}"
                if not candidate.exists():
                    target = candidate
                    break
        shutil.copytree(source, target)
        return target

    def _looks_like_session_dir(self, source: Path) -> bool:
        files = [p for p in source.iterdir() if p.is_file()]
        names = {p.name.lower() for p in files}
        known = {"raw_events.jsonl", "events.jsonl", "session.json", "session_meta.json", "settlement_report.json"}
        if names & known:
            return True
        return any(p.suffix.lower() in {".html", ".htm", ".json", ".jsonl", ".txt"} for p in files)

    def _safe_build_session_report(self, session_dir: Path) -> dict:
        try:
            report = core.build_settlement_report(session_dir)
            return report or {}
        except Exception:
            return {}

    def _session_segment_from_dir(self, session_dir: Path) -> dict:
        files = [p for p in session_dir.iterdir() if p.is_file()]
        first = min((p.stat().st_mtime for p in files), default=session_dir.stat().st_mtime)
        last = max((p.stat().st_mtime for p in files), default=session_dir.stat().st_mtime)
        return {
            "start_label": datetime.fromtimestamp(first).strftime("%Y-%m-%d %H:%M"),
            "end_label": datetime.fromtimestamp(last).strftime("%Y-%m-%d %H:%M"),
            "duration_minutes": max(0, int((last - first) / 60)),
            "event_count": "未知",
        }

    def _generate_selected(self) -> None:
        sel = self.split_tree.get_selection()
        if not sel:
            messagebox.showinfo("提示", "请先在分割 Session 列表中选择一条记录")
            return
        iid = sel[0]
        item = next(
            (s for s in self._split_sessions
             if str(s.get("row_iid") or s.get("idx")) == str(iid)),
            None)
        if not item:
            return

        session_dir = Path(item.get("session_dir", ""))
        if not session_dir.exists():
            messagebox.showerror("错误", f"Session 目录不存在: {session_dir}")
            return
        try:
            report = core.build_settlement_report(session_dir)
        except Exception as exc:
            messagebox.showerror("结算失败", str(exc))
            return

        if not report or not report.get("items"):
            messagebox.showinfo("提示", "该 Session 无有效结算数据")
            return

        try:
            core.upsert_income_memory(INCOME_MEMORY_PATH, report, session_dir)
            item["confirmed"] = True
            messagebox.showinfo("入账成功", "结算数据已写入收支统计")
            self._refresh_split_table()
        except Exception as exc:
            messagebox.showerror("入账失败", str(exc))

    def _batch_generate(self) -> None:
        sel = self.split_tree.get_selection()
        if not sel:
            messagebox.showinfo("提示", "请先在分割 Session 列表中选择要结算的记录")
            return
        success = 0
        failed = 0
        for iid in sel:
            item = next(
                (s for s in self._split_sessions
                 if str(s.get("row_iid") or s.get("idx")) == str(iid)),
                None)
            if not item or item.get("confirmed"):
                continue
            session_dir = Path(item.get("session_dir", ""))
            if not session_dir.exists():
                failed += 1
                continue
            try:
                report = core.build_settlement_report(session_dir)
                if report and report.get("items"):
                    core.upsert_income_memory(INCOME_MEMORY_PATH, report, session_dir)
                    item["confirmed"] = True
                    success += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
        self._refresh_split_table()
        messagebox.showinfo("批量结算完成",
                           f"成功：{success} 个，失败：{failed} 个。\n已入账的 Session 标为「已加入」。")
