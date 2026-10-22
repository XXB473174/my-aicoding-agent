@echo off
rem 用脚本自身位置推导项目根目录，避免写死盘符导致换机器后启动失败。
cd /d "%~dp0.."
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
.venv\Scripts\python.exe -m uvicorn agent.app:app --host 127.0.0.1 --port 2024
