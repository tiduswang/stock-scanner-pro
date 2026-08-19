@echo off
chcp 65001 >nul 2>&1
title 智能选股系统 Pro - 主程序
cd /d "%~dp0"

echo ============================================================
echo   智能选股系统 Pro - 主程序启动
echo   本脚本只负责启动 Web 服务，不安装依赖
echo ============================================================
echo.

echo [1/2] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 python，请先安装 Python 3.10+ 并加入 PATH
    echo 下载: https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version

echo.
echo [2/2] 轻量依赖自检（不安装，缺失时提示运行 install.bat）...
python -c "import fastapi, uvicorn, akshare, pandas, numpy, pypinyin, ollama" 2>nul
if errorlevel 1 (
    echo [警告] 依赖未就绪，请先运行依赖安装 App：
    echo   - 双击 install.bat
    echo   - 或: python installer.py
    echo.
    pause
    exit /b 1
)
echo 依赖就绪 ✅

echo.
echo ============================================================
echo   前端页面:   http://127.0.0.1:8888/
echo   API 文档:   http://127.0.0.1:8888/docs
echo   按 Ctrl+C 可停止服务
echo ============================================================
echo.

python -m uvicorn backend.main:app --host 0.0.0.0 --port 8888 --reload

pause
