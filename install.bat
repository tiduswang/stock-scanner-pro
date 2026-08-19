@echo off
chcp 65001 >nul 2>&1
title 智能选股系统 Pro - 依赖安装
cd /d "%~dp0"

echo ============================================================
echo   智能选股系统 Pro - 依赖安装 App
echo   本脚本只负责安装和检查依赖，不启动 Web 服务
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
echo [2/2] 安装依赖并自检（首次较慢，使用清华源加速）...
echo ============================================================
python installer.py
if errorlevel 1 (
    echo.
    echo [错误] 安装或自检失败，请查看上方日志
    echo        若为 numpy 冲突，请手动执行：
    echo        pip install --force-reinstall --no-deps numpy==2.1.2
    echo        然后再次运行 install.bat
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   安装完成！下一步请运行主程序：
echo     - 双击 start.bat
echo     - 或: python -m uvicorn backend.main:app --host 0.0.0.0 --port 8888 --reload
echo ============================================================
pause
