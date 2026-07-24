# -*- coding: utf-8 -*-
"""
小鹦鹉记账 - Modern Premium Dark Theme

Inspired by VS Code / Cursor dark UI with enhanced glass-morphism,
vibrant gradients, and premium micro-animation tokens.
"""
from __future__ import annotations


# ============================================
# 颜色系统 (Premium Dark Theme)
# ============================================

# ── 背景色 (3-tier depth system) ──
BG_APP = "#111113"               # L0: 最深 - 全局背景
BG_SIDEBAR = "#18181b"           # L0.5: 侧边栏
BG_CARD = "#1c1c20"              # L1: 卡片/容器
BG_CARD_ALT = "#212126"          # L1.5: 交替卡片
BG_INPUT = "#27272b"             # L2: 输入框
BG_HOVER = "#2a2a30"             # L2: 悬停态
BG_ACTIVE = "#303038"            # L2.5: 选中/活跃态
BG_ELEVATED = "#35353d"          # L3: 浮层/tooltip

# ── 强调色 (Vibrant Blue Gradient) ──
ACCENT_PRIMARY = "#3b82f6"       # 主蓝 (Tailwind blue-500)
ACCENT_PRIMARY_HOVER = "#60a5fa" # 亮蓝 hover
ACCENT_PRIMARY_DARK = "#2563eb"  # 深蓝 pressed
ACCENT_PRIMARY_GLOW = "#3b82f620"  # 蓝色辉光 (半透明)
ACCENT_SECONDARY = "#8b5cf6"     # 紫色副色 (Tailwind violet-500)
ACCENT_SUCCESS = "#22c55e"       # 成功绿 (Tailwind green-500)
ACCENT_WARNING = "#f59e0b"       # 警告黄 (Tailwind amber-500)
ACCENT_DANGER = "#ef4444"        # 危险红 (Tailwind red-500)

# ── 状态色背景 (低饱和度) ──
BG_SUCCESS = "#132719"
BG_WARNING = "#2a2213"
BG_DANGER = "#2d1515"

# ── 文字色 (4-level hierarchy) ──
TEXT_TITLE = "#f0f0f3"           # 一级: 标题 / 关键信息
TEXT_BODY = "#a1a1aa"            # 二级: 正文 (Tailwind zinc-400)
TEXT_MUTED = "#71717a"           # 三级: 次要文字 (Tailwind zinc-500)
TEXT_GHOST = "#52525b"           # 四级: 占位符/禁用 (Tailwind zinc-600)
TEXT_WHITE = "#ffffff"           # 纯白 (按钮/状态栏)
TEXT_ON_PRIMARY = "#ffffff"      # 主色上的文字

# ── 边框 ──
BORDER_DEFAULT = "#27272a"       # 默认边框 (Tailwind zinc-800)
BORDER_SUBTLE = "#1f1f23"        # 微妙边框
BORDER_FOCUS = "#3b82f6"         # 聚焦边框 (= ACCENT_PRIMARY)
BORDER_SEPARATOR = "#27272a"     # 分隔线

# ── 玻璃态 ──
GLASS_BG = "#1c1c2088"          # 半透明卡片背景
GLASS_BORDER = "#ffffff0a"      # 玻璃边框

# ============================================
# 字体系统
# ============================================

FONT_FAMILY = "Segoe UI"
FONT_FAMILY_MONO = "Cascadia Code"

F_TITLE = (FONT_FAMILY, 18, "bold")        # 页面大标题
F_SUBTITLE = (FONT_FAMILY, 14, "bold")      # 副标题
F_CARD_TITLE = (FONT_FAMILY, 13, "bold")    # 卡片标题
F_BODY = (FONT_FAMILY, 12)                  # 正文
F_BODY_BOLD = (FONT_FAMILY, 12, "bold")     # 正文加粗
F_SMALL = (FONT_FAMILY, 11)                 # 小字
F_TINY = (FONT_FAMILY, 10)                  # 微字
F_BUTTON = (FONT_FAMILY, 12)                # 按钮
F_BUTTON_LARGE = (FONT_FAMILY, 13, "bold")  # 大按钮
F_SIDEBAR = (FONT_FAMILY, 14)               # 侧边栏
F_SIDEBAR_ACTIVE = (FONT_FAMILY, 13, "bold")  # 侧边栏选中
F_SIDEBAR_GROUP = (FONT_FAMILY, 10, "bold")    # 侧边栏分组标题
F_STATUS = (FONT_FAMILY, 11)                # 状态栏
F_METRIC_VALUE = (FONT_FAMILY, 20, "bold")  # 数字指标
F_METRIC_LABEL = (FONT_FAMILY, 10)          # 指标标签

# ============================================
# 间距 / 圆角 / 布局
# ============================================

CORNER_RADIUS = 8                # 现代圆角
CORNER_RADIUS_SM = 6             # 小圆角
CORNER_RADIUS_LG = 12            # 大圆角
CORNER_RADIUS_XL = 16            # 超大圆角 (对话框)
SIDEBAR_WIDTH = 240
SIDEBAR_PADDING_X = 12
SIDEBAR_PADDING_Y = 4
CARD_PADDING = 20
STATUS_BAR_HEIGHT = 32
BUTTON_HEIGHT = 36
BUTTON_HEIGHT_LG = 42
INPUT_HEIGHT = 36

# ============================================
# 动画时间 (ms)
# ============================================

ANIM_FAST = 100
ANIM_NORMAL = 200
ANIM_SLOW = 350
ANIM_PAGE_TRANSITION = 200

# ============================================
# 阴影 (用于 Canvas 模拟)
# ============================================

SHADOW_COLOR = "#00000040"
SHADOW_OFFSET = 2

# ============================================
# 兼容性字典 (供旧代码引用)
# ============================================

COLORS = {
    # 核心背景
    "background": BG_APP,
    "sidebar": BG_SIDEBAR,
    "sidebar_hover": BG_HOVER,
    "sidebar_active_indicator": ACCENT_PRIMARY,
    "card": BG_CARD,
    "card_alt": BG_CARD_ALT,
    "card_shadow": SHADOW_COLOR,

    # 强调色
    "primary": ACCENT_PRIMARY,
    "primary_hover": ACCENT_PRIMARY_HOVER,
    "primary_dark": ACCENT_PRIMARY_DARK,
    "primary_light": BG_ACTIVE,
    "primary_glow": ACCENT_PRIMARY_GLOW,
    "secondary": ACCENT_SECONDARY,
    "success": ACCENT_SUCCESS,
    "success_light": BG_SUCCESS,
    "warning": ACCENT_WARNING,
    "warning_light": BG_WARNING,
    "danger": ACCENT_DANGER,
    "danger_light": BG_DANGER,

    # 文字
    "text_primary": TEXT_TITLE,
    "text_secondary": TEXT_BODY,
    "text_muted": TEXT_MUTED,
    "text_ghost": TEXT_GHOST,
    "text_on_primary": TEXT_ON_PRIMARY,
    "text_white": TEXT_WHITE,

    # 边框
    "border": BORDER_DEFAULT,
    "border_subtle": BORDER_SUBTLE,
    "border_focus": BORDER_FOCUS,
    "border_light": BORDER_DEFAULT,

    # 表格
    "table_header": BG_SIDEBAR,
    "table_header_text": TEXT_TITLE,
    "table_selected": ACCENT_PRIMARY_DARK,
    "table_selected_text": TEXT_WHITE,
    "table_alt": BG_CARD_ALT,
    "table_hover": BG_HOVER,

    # 输入
    "entry_bg": BG_INPUT,
    "entry_border": BORDER_DEFAULT,
    "entry_border_focus": BORDER_FOCUS,

    # 工具栏
    "toolbar_bg": BG_CARD,
    "toolbar_hover": BG_HOVER,

    # 提示
    "hint_bg": BG_CARD,
    "hint_text": TEXT_MUTED,
    "hint_border": BORDER_DEFAULT,

    # 状态栏
    "status_bar": ACCENT_PRIMARY,
    "status_bar_text": TEXT_WHITE,

    # 玻璃态
    "glass_bg": GLASS_BG,
    "glass_border": GLASS_BORDER,
}

FONTS = {
    "title": F_TITLE,
    "subtitle": F_SUBTITLE,
    "card_title": F_CARD_TITLE,
    "body": F_BODY,
    "body_bold": F_BODY_BOLD,
    "small": F_SMALL,
    "tiny": F_TINY,
    "button": F_BUTTON,
    "button_large": F_BUTTON_LARGE,
    "sidebar": F_SIDEBAR,
    "sidebar_active": F_SIDEBAR_ACTIVE,
    "sidebar_group": F_SIDEBAR_GROUP,
    "status": F_STATUS,
    "metric_value": F_METRIC_VALUE,
    "metric_label": F_METRIC_LABEL,
    "table": F_BODY,
    "table_header": F_BODY_BOLD,
}
