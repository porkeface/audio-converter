"""
音频转换工具 UI 模块

包含应用程序的图形用户界面组件。
"""

import customtkinter as ctk

# 尝试导入拖拽支持
try:
    from tkinterdnd2 import TkinterDnD
    DRAG_DROP_AVAILABLE = True
except ImportError:
    DRAG_DROP_AVAILABLE = False

from .styles import COLORS, OUTPUT_FORMATS, WINDOW_TITLE, WINDOW_SIZE
from .components import FileCard
from .app import AudioConverterUI

__all__ = [
    'COLORS',
    'OUTPUT_FORMATS',
    'WINDOW_TITLE',
    'WINDOW_SIZE',
    'FileCard',
    'AudioConverterUI',
    'main',
]


# 兼容性启动类
if DRAG_DROP_AVAILABLE:
    class CTkApp(ctk.CTk, TkinterDnD.DnDWrapper):
        def __init__(self):
            super().__init__()
            self.TkdndVersion = TkinterDnD._require(self)
else:
    class CTkApp(ctk.CTk):
        pass


def main():
    """启动 GUI 应用程序。"""
    # 默认跟随系统
    ctk.set_appearance_mode("System")
    app_root = CTkApp()
    app = AudioConverterUI(app_root)
    app_root.mainloop()
