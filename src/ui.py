"""
音频转换工具 - 图形界面 (GUI)
使用 tkinter 实现，支持文件拖拽和批量转换
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, Listbox
import threading
import os
from pathlib import Path
from typing import Optional, List
import sys

from .main import convert_ncm
from .utils.detector import detect_format


class AudioConverterUI:
    """音频转换工具主界面"""

    def __init__(self, root):
        self.root = root
        self.root.title("音频格式转换工具 (Audio Converter)")
        self.root.geometry("750x700")
        self.root.configure(bg='#f0f0f0')

        # 变量
        self.output_format = tk.StringVar(value="flac")
        self.status_text = tk.StringVar(value="就绪")
        self.input_files: List[str] = []  # 多文件列表

        # 创建界面
        self._create_widgets()

        # 启用拖拽支持
        self._enable_drag_and_drop()

        # 转换线程
        self.convert_thread: Optional[threading.Thread] = None
        self.converting = False

    def _create_widgets(self):
        """创建所有界面组件"""

        # 标题
        title_frame = tk.Frame(self.root, bg='#f0f0f0')
        title_frame.pack(fill='x', padx=20, pady=10)

        title_label = tk.Label(
            title_frame,
            text="🎵 音频格式转换工具",
            font=("Arial", 18, "bold"),
            bg='#f0f0f0',
            fg='#333'
        )
        title_label.pack()

        subtitle_label = tk.Label(
            title_frame,
            text="支持 NCM → FLAC / MP3 / WAV 转换 | 支持拖拽和批量转换",
            font=("Arial", 10),
            bg='#f0f0f0',
            fg='#666'
        )
        subtitle_label.pack(pady=(5, 0))

        # 主容器
        main_frame = tk.Frame(self.root, bg='white', relief='raised', borderwidth=1)
        main_frame.pack(fill='both', expand=True, padx=20, pady=10)

        # ========== 输入文件区域 ==========
        input_frame = tk.LabelFrame(main_frame, text="输入文件（支持多选和拖拽）", font=("Arial", 10, "bold"), bg='white')
        input_frame.pack(fill='both', expand=True, padx=15, pady=15)

        # 按钮区域
        button_frame = tk.Frame(input_frame, bg='white')
        button_frame.pack(fill='x', padx=10, pady=(10, 5))

        tk.Button(
            button_frame,
            text="📁 选择文件",
            command=self._select_input_files,
            bg='#4CAF50',
            fg='white',
            font=("Arial", 9),
            padx=15,
            cursor='hand2'
        ).pack(side='left', padx=5)

        tk.Button(
            button_frame,
            text="🗑️ 清空列表",
            command=self._clear_file_list,
            bg='#f44336',
            fg='white',
            font=("Arial", 9),
            padx=15,
            cursor='hand2'
        ).pack(side='left', padx=5)

        tk.Button(
            button_frame,
            text="❌ 移除选中",
            command=self._remove_selected,
            bg='#FF9800',
            fg='white',
            font=("Arial", 9),
            padx=15,
            cursor='hand2'
        ).pack(side='left', padx=5)

        # 文件列表
        list_frame = tk.Frame(input_frame, bg='white')
        list_frame.pack(fill='both', expand=True, padx=10, pady=(5, 10))

        # 滚动条
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')

        # 文件列表框
        self.file_listbox = Listbox(
            list_frame,
            selectmode=tk.EXTENDED,
            font=("Consolas", 9),
            bg='#fafafa',
            selectbackground='#2196F3',
            yscrollcommand=scrollbar.set
        )
        self.file_listbox.pack(fill='both', expand=True)
        scrollbar.config(command=self.file_listbox.yview)

        # 绑定双击事件（移除文件）
        self.file_listbox.bind('<Double-Button-1>', lambda e: self._remove_selected())

        # 拖拽提示标签
        self.drop_label = tk.Label(
            input_frame,
            text="💡 提示：可以直接拖拽文件到此处",
            font=("Arial", 8),
            bg='white',
            fg='#999'
        )
        self.drop_label.pack(pady=(0, 5))

        # ========== 输出选项 ==========
        output_frame = tk.LabelFrame(main_frame, text="输出选项", font=("Arial", 10, "bold"), bg='white')
        output_frame.pack(fill='x', padx=15, pady=(0, 15))

        # 输出格式
        format_frame = tk.Frame(output_frame, bg='white')
        format_frame.pack(fill='x', padx=10, pady=(10, 5))

        tk.Label(format_frame, text="输出格式:", font=("Arial", 9), bg='white').pack(side='left', padx=(5, 10))

        for fmt in ["flac", "mp3", "wav"]:
            tk.Radiobutton(
                format_frame,
                text=fmt.upper(),
                variable=self.output_format,
                value=fmt,
                font=("Arial", 9),
                bg='white',
                cursor='hand2'
            ).pack(side='left', padx=10)

        # 输出目录
        output_dir_frame = tk.Frame(output_frame, bg='white')
        output_dir_frame.pack(fill='x', padx=10, pady=(5, 10))

        tk.Label(output_dir_frame, text="输出目录:", font=("Arial", 9), bg='white').pack(side='left', padx=(5, 10))

        self.output_dir_var = tk.StringVar()
        self.output_dir_entry = tk.Entry(output_dir_frame, textvariable=self.output_dir_var, font=("Arial", 9))
        self.output_dir_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))

        tk.Button(
            output_dir_frame,
            text="浏览",
            command=self._select_output_dir,
            bg='#2196F3',
            fg='white',
            font=("Arial", 9),
            padx=10,
            cursor='hand2'
        ).pack(side='right', padx=(5, 0))

        # ========== 转换按钮 ==========
        button_frame2 = tk.Frame(main_frame, bg='white')
        button_frame2.pack(fill='x', padx=15, pady=(0, 15))

        self.convert_button = tk.Button(
            button_frame2,
            text="🚀 开始批量转换",
            command=self._start_convert,
            bg='#FF5722',
            fg='white',
            font=("Arial", 12, "bold"),
            padx=30,
            pady=10,
            cursor='hand2',
            relief='flat'
        )
        self.convert_button.pack(pady=10)

        # ========== 日志输出 ==========
        log_frame = tk.LabelFrame(main_frame, text="转换日志", font=("Arial", 10, "bold"), bg='white')
        log_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=12,
            font=("Consolas", 8),
            bg='#1e1e1e',
            fg='#d4d4d4',
            insertbackground='white'
        )
        self.log_text.pack(fill='both', expand=True, padx=10, pady=10)

        # ========== 状态栏 ==========
        status_bar = tk.Frame(self.root, bg='#333', height=25)
        status_bar.pack(fill='x', side='bottom')

        self.status_label = tk.Label(
            status_bar,
            textvariable=self.status_text,
            bg='#333',
            fg='white',
            font=("Arial", 9),
            anchor='w'
        )
        self.status_label.pack(fill='x', padx=10, pady=3)

    def _enable_drag_and_drop(self):
        """启用文件拖拽功能（Windows）"""
        try:
            # 使用 Windows API 实现拖拽
            import ctypes
            from ctypes import wintypes

            # 定义必要的 Windows API
            ole32 = ctypes.windll.ole32
            shell32 = ctypes.windll.shell32

            # 注册拖拽目标
            self.root.update_idletasks()
            hwnd = int(self.root.winfo_id())

            # 使用 tkinter 的 WM_DROPFILES 消息
            self.root.drop_target_register(tk.DND_FILES)
            self.root.dnd_bind('<<Drop>>', self._on_drop)
            self._log("[信息] 文件拖拽功能已启用")
        except Exception as e:
            self._log(f"[警告] 无法启用拖拽功能: {e}")
            self._log("[提示] 请使用 '选择文件' 按钮添加文件")

    def _on_drop(self, event):
        """处理文件拖拽事件"""
        files = self.root.tk.splitlist(event.data)
        for f in files:
            # 去掉可能的花括号（Windows 路径有时会有）
            f = f.strip('{}')
            if f and f not in self.input_files:
                self.input_files.append(f)
                self.file_listbox.insert(tk.END, Path(f).name)
                self._log(f"[添加文件] {Path(f).name}")
        self._update_status(f"已添加 {len(self.input_files)} 个文件")

    def _select_input_files(self):
        """选择多个输入文件"""
        filenames = filedialog.askopenfilenames(
            title="选择音频文件（可多选）",
            filetypes=[
                ("NCM 文件", "*.ncm"),
                ("所有支持的格式", "*.ncm"),
                ("所有文件", "*.*")
            ]
        )
        if filenames:
            for f in filenames:
                if f not in self.input_files:
                    self.input_files.append(f)
                    self.file_listbox.insert(tk.END, Path(f).name)
                    self._log(f"[添加文件] {Path(f).name}")

            self._update_status(f"已添加 {len(self.input_files)} 个文件")

            # 自动设置输出目录为第一个文件的目录
            if not self.output_dir_var.get() and self.input_files:
                output_dir = Path(self.input_files[0]).parent
                self.output_dir_var.set(str(output_dir))
                self._log(f"[输出目录] {output_dir}")

    def _clear_file_list(self):
        """清空文件列表"""
        self.input_files.clear()
        self.file_listbox.delete(0, tk.END)
        self._log("[清空] 文件列表已清空")
        self._update_status("就绪")

    def _remove_selected(self):
        """移除选中的文件"""
        selected = list(self.file_listbox.curselection())
        selected.reverse()  # 从后往前删除，避免索引错乱
        for index in selected:
            file_path = self.input_files[index]
            self._log(f"[移除文件] {Path(file_path).name}")
            self.file_listbox.delete(index)
            del self.input_files[index]

        self._update_status(f"剩余 {len(self.input_files)} 个文件")

    def _select_output_dir(self):
        """选择输出目录"""
        directory = filedialog.askdirectory(title="选择输出目录")
        if directory:
            self.output_dir_var.set(directory)
            self._log(f"[输出目录] {directory}")

    def _log(self, message: str):
        """添加日志"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def _update_status(self, text: str):
        """更新状态栏"""
        self.status_text.set(text)
        self.root.update_idletasks()

    def _start_convert(self):
        """开始批量转换"""
        if not self.input_files:
            messagebox.showerror("错误", "请先添加要转换的文件！")
            return

        if self.converting:
            messagebox.showwarning("警告", "正在转换中，请等待...")
            return

        # 确定输出目录
        output_dir = self.output_dir_var.get()
        if not output_dir:
            # 默认使用第一个文件的目录
            output_dir = Path(self.input_files[0]).parent
            self.output_dir_var.set(str(output_dir))

        if not Path(output_dir).exists():
            messagebox.showerror("错误", f"输出目录不存在:\n{output_dir}")
            return

        # 禁用按钮，防止重复点击
        self.converting = True
        self.convert_button.config(state='disabled', text="转换中...")
        self._update_status("正在批量转换...")

        # 在新线程中执行转换
        self.convert_thread = threading.Thread(
            target=self._batch_convert_worker,
            args=(output_dir,),
            daemon=True
        )
        self.convert_thread.start()

    def _batch_convert_worker(self, output_dir: str):
        """批量转换工作线程"""
        total = len(self.input_files)
        success_count = 0
        fail_count = 0

        self._log("=" * 60)
        self._log(f"[开始] 批量转换 {total} 个文件")
        self._log(f"[输出目录] {output_dir}")
        self._log(f"[输出格式] {self.output_format.get().upper()}")
        self._log("=" * 60)

        for index, input_path in enumerate(self.input_files, 1):
            try:
                self._log(f"\n[{index}/{total}] 处理: {Path(input_path).name}")

                # 生成输出文件路径
                base_name = Path(input_path).stem
                output_path = str(Path(output_dir) / f"{base_name}.{self.output_format.get()}")

                # 重定向 print 输出到日志
                import sys
                from io import StringIO

                old_stdout = sys.stdout
                sys.stdout = StringIO()

                # 执行转换
                result = convert_ncm(input_path, output_path, output_format=self.output_format.get())

                # 恢复 stdout 并获取输出
                output = sys.stdout.getvalue()
                sys.stdout = old_stdout

                # 显示输出
                if output:
                    for line in output.strip().split('\n'):
                        if line.strip():
                            self._log(f"  {line}")

                success_count += 1
                self._log(f"[成功] ✓ {Path(input_path).name}")

            except Exception as e:
                fail_count += 1
                self._log(f"[失败] ✗ {Path(input_path).name}")
                self._log(f"  错误: {e}")
                import traceback
                self._log(traceback.format_exc())

        # 转换完成
        self.root.after(0, self._on_batch_complete, success_count, fail_count)

    def _on_batch_complete(self, success_count: int, fail_count: int):
        """批量转换完成回调"""
        self.converting = False
        self.convert_button.config(state='normal', text="🚀 开始批量转换")
        self._update_status(f"转换完成！成功: {success_count}, 失败: {fail_count}")

        messagebox.showinfo(
            "批量转换完成",
            f"转换完成！\n\n成功: {success_count} 个文件\n失败: {fail_count} 个文件"
        )

        self._log("=" * 60)
        self._log(f"[完成] 成功: {success_count}, 失败: {fail_count}")
        self._log("=" * 60)


def main():
    """启动 GUI"""
    root = tk.Tk()
    app = AudioConverterUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
