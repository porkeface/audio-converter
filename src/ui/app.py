"""
音频转换工具 - 主应用模块

采用动态色彩元组，支持 Light/Dark 模式自动切换。
"""

import threading
from pathlib import Path
from typing import Dict, Optional

import customtkinter as ctk
from tkinter import filedialog, messagebox

# 尝试导入拖拽支持
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DRAG_DROP_AVAILABLE = True
except ImportError:
    DRAG_DROP_AVAILABLE = False

from ..main import convert_file, get_metadata_str, get_metadata_from_file
from ..utils.detector import detect_format
from .components import FileCard
from .styles import COLORS, OUTPUT_FORMATS, WINDOW_TITLE, WINDOW_SIZE


class AudioConverterUI:
    """音频转换工具主界面。

    Attributes:
        root: 顶层窗口。
        output_format: 输出格式变量。
        input_files: 输入文件字典，键为文件路径，值为 FileCard。
        converting: 是否正在转换。
    """

    def __init__(self, root: ctk.CTk) -> None:
        """初始化主界面。

        Args:
            root: 顶层窗口。
        """
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry(WINDOW_SIZE)

        # 使用动态背景色
        self.root.configure(fg_color=COLORS["bg_main"])

        # 变量
        self.output_format = ctk.StringVar(value="默认")
        self.input_files: Dict[str, FileCard] = {}
        self.converting = False

        self._setup_layout()
        self._create_sidebar()
        self._create_main_area()

        if DRAG_DROP_AVAILABLE:
            self._enable_drag_and_drop()

        self._update_empty_state()

    def _setup_layout(self) -> None:
        """设置主布局。"""
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

    def _create_sidebar(self) -> None:
        """创建侧边栏。"""
        self.sidebar = ctk.CTkFrame(
            self.root,
            width=240,
            corner_radius=0,
            fg_color=COLORS["bg_sidebar"],
            border_width=0,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(10, weight=1)

        # Logo
        self.logo = ctk.CTkLabel(
            self.sidebar,
            text="AUDIO\nPRO",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=COLORS["accent"],
        )
        self.logo.grid(row=0, column=0, padx=30, pady=(40, 40))

        # Format Selection
        ctk.CTkLabel(
            self.sidebar,
            text="输出格式",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["text_dim"],
        ).grid(row=1, column=0, padx=30, pady=(10, 10), sticky="w")

        for i, fmt in enumerate(OUTPUT_FORMATS):
            rb = ctk.CTkRadioButton(
                self.sidebar,
                text=fmt.upper(),
                variable=self.output_format,
                value=fmt,
                border_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                text_color=COLORS["text_main"],
            )
            rb.grid(row=2 + i, column=0, padx=35, pady=8, sticky="w")

        # Appearance
        ctk.CTkLabel(
            self.sidebar,
            text="外观界面",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["text_dim"],
        ).grid(row=7, column=0, padx=30, pady=(30, 10), sticky="w")

        self.theme_menu = ctk.CTkOptionMenu(
            self.sidebar,
            values=["System", "Dark", "Light"],
            fg_color=COLORS["card_bg"],
            button_color=COLORS["card_bg"],
            button_hover_color=COLORS["border"],
            text_color=COLORS["text_main"],
            command=ctk.set_appearance_mode,
        )
        self.theme_menu.grid(row=8, column=0, padx=30, pady=0, sticky="w")
        self.theme_menu.set("System")

    def _create_main_area(self) -> None:
        """创建主内容区域。"""
        self.main_container = ctk.CTkFrame(self.root, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=30, pady=30)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(1, weight=1)

        # Header
        self.header = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.header.grid(row=0, column=0, sticky="ew", pady=(0, 20))

        self.title_label = ctk.CTkLabel(
            self.header,
            text="文件列表",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLORS["text_main"],
        )
        self.title_label.pack(side="left")

        self.add_btn = ctk.CTkButton(
            self.header,
            text="+ 添加文件",
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._select_files,
            width=100,
        )
        self.add_btn.pack(side="right", padx=5)

        self.clear_btn = ctk.CTkButton(
            self.header,
            text="清空",
            fg_color="transparent",
            border_width=1,
            border_color=COLORS["border"],
            text_color=COLORS["text_main"],
            hover_color=COLORS["danger"],
            command=self._clear_list,
            width=60,
        )
        self.clear_btn.pack(side="right", padx=5)

        # Scrollable Area
        self.scroll_frame = ctk.CTkScrollableFrame(
            self.main_container, fg_color="transparent"
        )
        self.scroll_frame.grid(row=1, column=0, sticky="nsew")

        # Empty State Placeholder
        self.empty_label = ctk.CTkLabel(
            self.main_container,
            text="✨\n拖拽文件到这里开始\n或点击添加按钮",
            font=ctk.CTkFont(size=16),
            text_color=COLORS["text_dim"],
        )

        # Footer Area
        self.footer = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.footer.grid(row=2, column=0, sticky="ew", pady=(20, 0))

        # Path Selector
        self.path_frame = ctk.CTkFrame(
            self.footer,
            fg_color=COLORS["card_bg"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
        )
        self.path_frame.pack(fill="x", pady=(0, 20))

        self.path_var = ctk.StringVar(value="默认输出至原文件夹")
        self.path_entry = ctk.CTkEntry(
            self.path_frame,
            textvariable=self.path_var,
            border_width=0,
            fg_color="transparent",
            text_color=COLORS["text_main"],
            placeholder_text="输出目录",
            height=40,
        )
        self.path_entry.pack(side="left", fill="x", expand=True, padx=15)

        self.browse_btn = ctk.CTkButton(
            self.path_frame,
            text="更改目录",
            fg_color=COLORS["border"],
            hover_color=COLORS["accent"],
            text_color=COLORS["text_main"],
            width=80,
            height=30,
            command=self._select_output_dir,
        )
        self.browse_btn.pack(side="right", padx=10)

        # Action Button & Progress
        self.convert_btn = ctk.CTkButton(
            self.footer,
            text="开始转换全部文件",
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            height=50,
            command=self._start_conversion,
        )
        self.convert_btn.pack(fill="x")

        self.progress = ctk.CTkProgressBar(
            self.footer, progress_color=COLORS["accent"], height=4
        )
        self.progress.pack(fill="x", pady=(15, 0))
        self.progress.set(0)

    def _update_empty_state(self) -> None:
        """更新空状态显示。"""
        if not self.input_files:
            self.empty_label.place(relx=0.5, rely=0.4, anchor="center")
            self.scroll_frame.grid_remove()
        else:
            self.empty_label.place_forget()
            self.scroll_frame.grid()

    def _add_file_to_ui(self, path: str) -> None:
        """添加文件到 UI 列表。

        Args:
            path: 文件路径。
        """
        if path in self.input_files:
            return

        card = FileCard(self.scroll_frame, path, self._remove_file)
        card.pack(fill="x", pady=6, padx=5)
        self.input_files[path] = card
        self._update_empty_state()

    def _remove_file(self, card: FileCard) -> None:
        """从列表中移除文件。

        Args:
            card: 要移除的 FileCard 组件。
        """
        path = card.file_path
        card.destroy()
        if path in self.input_files:
            del self.input_files[path]
        self._update_empty_state()

    def _clear_list(self) -> None:
        """清空文件列表。"""
        for card in self.input_files.values():
            card.destroy()
        self.input_files.clear()
        self._update_empty_state()
        self.progress.set(0)

    def _select_files(self) -> None:
        """打开文件选择对话框。"""
        files = filedialog.askopenfilenames(
            title="选择音频文件",
            filetypes=[("加密音频", "*.ncm *.mflac *.mgg"), ("所有文件", "*.*")],
        )
        for f in files:
            self._add_file_to_ui(f)

    def _select_output_dir(self) -> None:
        """打开输出目录选择对话框。"""
        d = filedialog.askdirectory()
        if d:
            self.path_var.set(d)

    def _enable_drag_and_drop(self) -> None:
        """启用拖拽功能。"""
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind(
            '<<Drop>>',
            lambda e: [
                self._add_file_to_ui(f.strip('{}'))
                for f in self.root.splitlist(e.data)
            ],
        )

    def _start_conversion(self) -> None:
        """开始转换任务。"""
        if not self.input_files or self.converting:
            return

        self.converting = True
        self.convert_btn.configure(state="disabled", text="正在处理...")
        self.add_btn.configure(state="disabled")

        # 在主线程中获取 tkinter 变量的值
        out_dir = self.path_var.get()
        if out_dir == "默认输出至原文件夹":
            out_dir = None

        fmt_choice = self.output_format.get()

        # 获取文件列表的快照
        files = list(self.input_files.items())

        threading.Thread(
            target=self._conversion_worker,
            args=(out_dir, fmt_choice, files),
            daemon=True,
        ).start()

    def _conversion_worker(
        self,
        out_dir: Optional[str],
        fmt_choice: str,
        files: list,
    ) -> None:
        """转换工作线程。

        Args:
            out_dir: 输出目录，None 表示使用原文件目录。
            fmt_choice: 输出格式选择。
            files: 文件列表，每个元素是 (path, card) 元组。
        """
        total = len(files)

        for i, (path, card) in enumerate(files):
            # 使用 after 在主线程中更新 UI
            self.root.after(0, lambda c=card: c.set_status("正在转换...", COLORS["accent"]))
            try:
                final_out = out_dir or str(Path(path).parent)
                if fmt_choice == "默认":
                    output_path = str(Path(final_out) / Path(path).stem)
                else:
                    output_path = str(Path(final_out) / f"{Path(path).stem}.{fmt_choice}")

                actual_output = convert_file(path, output_path)
                if actual_output:
                    # 解密后提取元数据并显示在卡片上
                    meta_str = ""
                    try:
                        fmt = detect_format(path)
                        if fmt:
                            meta_str = get_metadata_str(fmt)
                    except Exception:
                        pass
                    # NCM 元数据为空时，从输出文件读取（适用于 MGG/OGG 等）
                    if not meta_str:
                        try:
                            meta_str = get_metadata_from_file(actual_output)
                        except Exception:
                            pass
                    if meta_str:
                        self.root.after(0, lambda c=card, m=meta_str: c.set_detail(m))
                    self.root.after(
                        0, lambda c=card: c.set_status("✓ 已完成", COLORS["success"])
                    )
                else:
                    self.root.after(
                        0, lambda c=card: c.set_status("✗ 失败", COLORS["danger"])
                    )
            except Exception:
                self.root.after(
                    0, lambda c=card: c.set_status("✗ 失败", COLORS["danger"])
                )

            self.root.after(0, lambda p=(i + 1) / total: self.progress.set(p))

        self.root.after(0, self._on_finish)

    def _on_finish(self) -> None:
        """转换完成回调。"""
        self.converting = False
        self.convert_btn.configure(state="normal", text="开始转换全部文件")
        self.add_btn.configure(state="normal")
        messagebox.showinfo("转换完成", "所有任务已处理完毕！")
