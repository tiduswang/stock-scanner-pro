@echo off
chcp 65001 >nul 2>&1
title 智能选股系统 Pro
cd /d "%~dp0"

echo ============================================================
echo   智能选股系统 Pro - 启动中...
echo ============================================================
echo.

echo [1/3] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 python，请先安装 Python 3.10+ 并加入 PATH
    echo 下载: https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version

echo.
echo [2/3] 安装依赖（首次启动较慢，使用清华源加速）...
python -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn -r requirements.txt
if errorlevel 1 (
    echo [警告] 清华源安装失败，尝试官方源...
    python -m pip install -r requirements.txt
)

echo.
echo [3/3] 启动 Web 服务...
echo ============================================================
echo   前端页面:   http://127.0.0.1:8888/
echo   API 文档:   http://127.0.0.1:8888/docs
echo   按 Ctrl+C 可停止服务
echo ============================================================
echo.

python -m uvicorn backend.main:app --host 0.0.0.0 --port 8888 --reload

pause
