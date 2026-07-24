# JX3 Click/Team Monitor MVP

独立实现的“开拍/开团监控”核心模块 MVP。

它不注入游戏、不修改游戏文件，只读取剑网3本地聊天 SQLite 日志：

`<JX3路径>\interface\my#data\**\userdata\chat_log\chatlog_*.v2.db`

## 桌面版运行

已打包 exe：

```text
jx3_click_monitor\dist\小鹦鹉记账\小鹦鹉记账.exe
```

分发压缩包：

```text
jx3_click_monitor\dist\小鹦鹉记账-v0.3.9.zip
```

源码方式双击：

```text
jx3_click_monitor\启动金团监控.bat
```

或命令行启动 GUI：

```powershell
C:\Users\litia\AppData\Local\Python\bin\python.exe .\jx3_click_monitor\jx3_click_monitor.py app
```

界面功能：

- 选择剑三 `zhcn_hd` 路径
- 选择输出目录
- 开始/停止实时监控
- 复用已有 session
- 离线扫描指定时间段，支持开始/结束时间选择器（年月日时分秒微调），也兼容手动填写 `2026-06-13` + `02:03:30` 或粘贴 `[Sat 2026-06-13 03:29 GMT+8]`
- 生成 JSON/Markdown 结算报告
- 应用内查看报告：不跳外部编辑器，直接弹窗显示并支持复制/保存
- 应用内查看表格：汇总、买家、成交、0 金记录分页展示，并可保存 CSV
- 当前账号/角色识别：从 GUI 的剑三 `zhcn_hd` 路径下扫描 `interface\my#data`，选择最近活跃角色目录，读取 `info.jx3dat`/`userdata.db` 得到登录账号、角色名、区服、uid
- 导入聊天 HTML：支持剑三导出的 `export\ChatLog\*.html`，转换成 session 后可继续解析/分割
- Session 解析/分割：按聊天时间断档识别多场团，选中一段拆成新的独立 session
- 自动记住上次路径和设置
- 打开报告和 session 文件夹
- 表格展示买家、合计金额、购买物品

## 功能

- 创建 session
- 增量扫描 `ChatLog` 表
- 输出原始事件 JSONL
- 输出简单 summary
- 停止时补扫
- 业务解析：拍卖开始、叫价、物品获得、金币获得、团队消息

## 快速验证

```powershell
C:\Users\litia\AppData\Local\Python\bin\python.exe .\jx3_click_monitor\jx3_click_monitor.py offline-scan --jx3-path "F:\JX3\Game\JX3\bin\zhcn_hd" --out-dir .\jx3_click_monitor\runs\test --start-ts 1781233705 --end-ts 1781236612
```

## 实时使用

```powershell
# 开始
C:\Users\litia\AppData\Local\Python\bin\python.exe .\jx3_click_monitor\jx3_click_monitor.py start --jx3-path "F:\JX3\Game\JX3\bin\zhcn_hd" --out-dir .\jx3_click_monitor\runs\live

# 增量扫描一次
C:\Users\litia\AppData\Local\Python\bin\python.exe .\jx3_click_monitor\jx3_click_monitor.py poll --session-dir .\jx3_click_monitor\runs\live\<session_id>

# 停止并补扫
C:\Users\litia\AppData\Local\Python\bin\python.exe .\jx3_click_monitor\jx3_click_monitor.py stop --session-dir .\jx3_click_monitor\runs\live\<session_id>
```

## 业务解析

对已有 session 重新解析：

```powershell
C:\Users\litia\AppData\Local\Python\bin\python.exe .\jx3_click_monitor\jx3_click_monitor.py analyze --session-dir .\jx3_click_monitor\runs\test\1781254306
```

生成金团结算 JSON 报告：

```powershell
C:\Users\litia\AppData\Local\Python\bin\python.exe .\jx3_click_monitor\jx3_click_monitor.py settlement --session-dir .\jx3_click_monitor\runs\test\1781254306
```

生成可读 Markdown 账单：

```powershell
C:\Users\litia\AppData\Local\Python\bin\python.exe .\jx3_click_monitor\jx3_click_monitor.py report --session-dir .\jx3_click_monitor\runs\test\1781254306
```

导出 CSV：

```powershell
C:\Users\litia\AppData\Local\Python\bin\python.exe .\jx3_click_monitor\jx3_click_monitor.py export-csv --session-dir .\jx3_click_monitor\runs\test\1781254306
```

指定实际分工资人数，例如 25 人：

```powershell
C:\Users\litia\AppData\Local\Python\bin\python.exe .\jx3_click_monitor\jx3_click_monitor.py settlement --session-dir .\jx3_click_monitor\runs\test\1781254306 --member-count 25
```

实时监控模式：

```powershell
C:\Users\litia\AppData\Local\Python\bin\python.exe .\jx3_click_monitor\jx3_click_monitor.py watch --jx3-path "F:\JX3\Game\JX3\bin\zhcn_hd" --out-dir .\jx3_click_monitor\runs\live --interval 2
```

复用已有 session：

```powershell
C:\Users\litia\AppData\Local\Python\bin\python.exe .\jx3_click_monitor\jx3_click_monitor.py watch --session-dir .\jx3_click_monitor\runs\test\1781254306 --interval 2
```

`poll`、`stop`、`offline-scan` 也会自动更新业务解析产物。

### 兼容结算规则

当前结算解析已补充这些兼容逻辑：

- 跨 DB 去重：同一秒、同频道、同文本/富文本只保留一条，避免多聊天库重复统计。
- 富文本解析：会把 `msg` 里的 `<text>text="..."</text>` 节点拼成纯文本，解决 text 列不完整/格式差异问题。
- 最终购买公告优先：解析 `[玩家]花费[金额]购买了[物品]` 和 `[玩家]花费[金额]帮[玩家]购买了[物品]`。
- 工资条完整性校验：要求总收入、补贴、实际可分配、分配人数、底薪五项齐全，并校验 `总收入-补贴=实际可分配`、`实际可分配/人数≈底薪`。
- 重拍/重新开拍过滤：把每次“开始拍卖”作为独立实例，叫价归入最近一次实例；同名物品重拍时，fallback 只保留最后一个有叫价的实例。
- 购买公告与叫价合并：非 0 金最终购买公告优先；0 金购买视为拾取/分配记录；若 0 金记录或缺失记录对应有拍卖叫价，则用拍卖实例最高价补账。
- 到账核对：用 `MSG_MONEY` 的金/银/铜精确换算，与底薪做粗核对，输出 `wage_receipt_check`。
- 缺口提示：输出 `purchase_total_vs_settlement_diff_gold`，用于提示已解析成交总额与工资条总收入的差额。

## 输出文件

- `session_meta.json`：session 元信息
- `active_session.json`：活动状态
- `state.json`：每个 db 的扫描游标
- `raw_events.jsonl`：原始聊天事件
- `business_events.jsonl`：结构化业务事件
- `summary.json`：类型统计、数量、时间范围
- `auction_summary.json`：拍卖/叫价/最高价/物品获得/金币获得汇总
- `settlement_report.json`：金团结算报告，包含谁买了什么、总金、补贴、实际可分配、平均工资、到账核对、重拍过滤结果

## 备注

这是干净实现版 MVP，只实现监控核心和原始事件收集。后续可继续加：

- 物品/金币/工资事件抽取
- 拍卖喊价解析
- 团队成员识别
- GUI 页面
- 自动常驻轮询
