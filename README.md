# JX3 Click/Team Monitor (小鹦鹉记账)

独立实现的剑网3“金团开拍/开团监控与自动记账”工具。

它不注入游戏、不修改游戏文件，仅只读解析剑网3本地聊天 SQLite 日志：

`<JX3路径>\interface\my#data\**\userdata\chat_log\chatlog_*.v2.db`

## 🚀 快速开始

### 1. 软件下载（推荐普通用户）
可以直接前往本仓库的 [Releases 页面](https://github.com/litiao1224/JX3Monitor/releases) 下载最新发布的桌面版绿色免安装压缩包或 `.exe` 独立运行程序。

### 2. 源码运行（适合开发者）
依赖环境：Python 3.10+

```powershell
# 克隆仓库
git clone https://github.com/litiao1224/JX3Monitor.git
cd JX3Monitor

# 安装依赖
pip install customtkinter Pillow

# 启动 GUI 桌面应用
python src/main.py
```

---

## 界面核心功能

- **游戏路径自动感知**：自动读取剑三 `zhcn_hd` 路径与数据目录
- **角色与区服智能识别**：自动读取最近活跃角色、账号、区服与门派信息
- **实时监控与小退结算**：开始/停止金团实时监控，支持小退写盘后自动生成结算报告
- **智能记账与缺口核对**：汇总买家、拍品成交额、平均工资、到账比对与缺口分析
- **收支历史与成长数据**：SQLite 存储历史记账，分析角色秘境CD与周刷新进度
- **聊天记录 HTML 导入**：支持解析剑三导出的 `export\ChatLog\*.html` 聊天文件
- **导出与保存**：支持生成并导出 CSV / Markdown 结算财务报表

---

## 命令行 (CLI) 使用说明

### 1. 离线扫描指定时间段

```powershell
python jx3_click_monitor.py offline-scan --jx3-path "D:\JX3\Game\JX3\bin\zhcn_hd" --out-dir .\runs\test --start-ts 1781233705 --end-ts 1781236612
```

### 2. 实时监控

```powershell
# 开始实时采集
python jx3_click_monitor.py start --jx3-path "D:\JX3\Game\JX3\bin\zhcn_hd" --out-dir .\runs\live

# 增量轮询一次
python jx3_click_monitor.py poll --session-dir .\runs\live\<session_id>

# 停止并总结结算
python jx3_click_monitor.py stop --session-dir .\runs\live\<session_id>
```

### 3. 业务解析与报表生成

```powershell
# 对已有会话重新分析
python jx3_click_monitor.py analyze --session-dir .\runs\test\<session_id>

# 生成金团结算 JSON 报告
python jx3_click_monitor.py settlement --session-dir .\runs\test\<session_id>

# 生成 Markdown 财务账单
python jx3_click_monitor.py report --session-dir .\runs\test\<session_id>

# 导出 CSV 表格
python jx3_click_monitor.py export-csv --session-dir .\runs\test\<session_id>
```

---

## 兼容结算规则

当前结算解析包含以下核心兼容逻辑：

- **跨 DB 增量去重**：同一秒、同频道、同文本/富文本只保留一条，避免多数据库重复统计。
- **富文本格式提取**：解析 `msg` 里的 `<text>text="..."</text>` 节点拼成纯文本，解决格式差异。
- **最终购买公告优先**：解析 `[玩家]花费[金额]购买了[物品]` 和 `[玩家]花费[金额]帮[玩家]购买了[物品]`。
- **工资条完整性校验**：要求总收入、补贴、实际可分配、分配人数、底薪五项齐全，校验 `总收入-补贴=实际可分配`。
- **重拍/重新开拍过滤**：把每次“开始拍卖”作为独立实例，同名物品重拍时自动只保留最后一次有效喊价。
- **到账核对**：用 `MSG_MONEY` 的金/银/铜精确换算，与底薪做核对，输出 `wage_receipt_check`。

---

## 会话输出结构

- `session_meta.json`：会话元信息
- `raw_events.jsonl`：原始聊天事件日志
- `business_events.jsonl`：结构化业务事件日志
- `auction_summary.json`：拍卖/叫价/最高价/物品获得/金币获得汇总
- `settlement_report.json`：金团结算报告（包含成交明细、总金、补贴、可分配、平均工资、到账核对）
