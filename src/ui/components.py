"""
UI 组件模块

定义可复用的 UI 组件，如 FileCard 等。
"""

import os
from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk

from .styles import COLORS


class FileCard(ctk.CTkFrame):
    """文件项卡片组件。

    用于在文件列表中显示单个文件的信息，包括文件名、大小、格式和状态。

    Attributes:
        file_path: 文件的完整路径。
        path_obj: Path 对象。
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        file_path: str,
        on_delete: Callable[['FileCard'], None],
    ) -> None:
        """初始化文件卡片。

        Args:
            master: 父组件。
            file_path: 文件完整路径。
            on_delete: 删除按钮的回调函数。
        """
        super().__init__(
            master,
            fg_color=COLORS["card_bg"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
        )
        self.file_path = file_path
        self.path_obj = Path(file_path)

        # 布局
        self.grid_columnconfigure(1, weight=1)

        # 图标
        self.icon_label = ctk.CTkLabel(self, text="🎵", font=("Segoe UI Emoji", 20))
        self.icon_label.grid(row=0, column=0, padx=(15, 10), pady=12)

        # 文件信息区域
        self.info_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.info_frame.grid(row=0, column=1, sticky="nsew", pady=10)

        self.name_label = ctk.CTkLabel(
            self.info_frame,
            text=self.path_obj.name,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text_main"],
            anchor="w",
        )
        self.name_label.pack(fill="x")

        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        self.detail_label = ctk.CTkLabel(
            self.info_frame,
            text=f"{self.path_obj.suffix.upper()} · {size_mb:.2f} MB",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"],
            anchor="w",
        )
        self.detail_label.pack(fill="x")

        # 状态标签
        self.status_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"],
        )
        self.status_label.grid(row=0, column=2, padx=10)

        # 删除按钮
        self.del_btn = ctk.CTkButton(
            self,
            text="✕",
            width=28,
            height=28,
            fg_color="transparent",
            hover_color=COLORS["danger"],
            text_color=COLORS["text_dim"],
            command=lambda: on_delete(self),
        )
        self.del_btn.grid(row=0, column=3, padx=(0, 15))

    def set_status(self, text: str, color: Optional[str] = None) -> None:
        """设置状态标签文本。

        Args:
            text: 状态文本。
            color: 文本颜色，None 使用默认颜色。
        """
        self.status_label.configure(text=text, text_color=color or COLORS["text_dim"])

    def set_detail(self, text: str) -> None:
        """设置详情标签文本。

        Args:
            text: 详情文本（如元数据信息）。
        """
        self.detail_label.configure(text=text)
