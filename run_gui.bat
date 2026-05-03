@echo off
chcp 65001 >nul
echo 正在启动音频转换工具 GUI...
echo.

cd /d "D:\codeProject\audio-converter"

uv run python gui.py

if errorlevel 1 (
    echo.
    echo 程序运行出错！
    pause
)
