@echo off
chcp 65001 >nul
start "Backend" cmd /k "cd /d %~dp0 && uvicorn main_rest_api:app --host 0.0.0.0 --port 8001"
timeout /t 8 /nobreak >nul
start "Frontend" cmd /k "cd /d %~dp0MediScanner-frontend && npm run dev"
pause
