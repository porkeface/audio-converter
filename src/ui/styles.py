"""
UI 样式配置模块

定义应用程序的颜色方案和主题配置。
"""

from typing import Tuple


# 动态全局样式配置 (Light, Dark)
# 格式: (Light Mode, Dark Mode)
COLORS = {
    "bg_main": ("#F5F5F7", "#121212"),
    "bg_sidebar": ("#EBEBEB", "#1A1A1A"),
    "card_bg": ("#FFFFFF", "#252525"),
    "accent": ("#3B82F6", "#3B82F6"),
    "accent_hover": ("#2563EB", "#2563EB"),
    "danger": ("#EF4444", "#EF4444"),
    "success": ("#10B981", "#10B981"),
    "text_main": ("#1A1A1A", "#F3F4F6"),
    "text_dim": ("#6B7280", "#9CA3AF"),
    "border": ("#D1D5DB", "#374151"),
}


def get_color(color_name: str) -> Tuple[str, str]:
    """获取颜色配置。

    Args:
        color_name: 颜色名称，必须是 COLORS 字典中的键。

    Returns:
        Tuple of (light_mode_color, dark_mode_color)。

    Raises:
        KeyError: 如果颜色名称不存在。
    """
    if color_name not in COLORS:
        raise KeyError(f"Unknown color: {color_name}")
    return COLORS[color_name]


# 支持的输出格式列表
OUTPUT_FORMATS = ["默认", "flac", "mp3", "wav", "m4a"]

# 应用程序窗口配置
WINDOW_TITLE = "Audio Converter Pro"
WINDOW_SIZE = "1000x720"
