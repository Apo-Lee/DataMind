@echo off
chcp 65001 > nul

echo ========================================
echo   DataMind - Starting Services
echo ========================================
echo.

REM Kill any existing python processes on our ports
echo [1/4] Cleaning up old processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
  if not "%%a"=="" (
    echo   Killing PID %%a on port 8000
    taskkill /F /PID %%a 2>nul
  )
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173') do (
  if not "%%a"=="" (
    echo   Killing PID %%a on port 5173
    taskkill /F /PID %%a 2>nul
  )
)
timeout /t 2 /nobreak > nul

REM Start backend
echo [2/4] Starting Backend (port 8000)...
cd /d "E:\Python_Code_Project\DataMind\backend"
set SECRET_KEY=test-secret-key-for-dev-ok
set ENCRYPTION_KEY=test-encryption-key-32chr
set DEEPSEEK_API_KEY=sk-test
set DEPLOYMENT_ENV=development
start "DataMind-Backend" /B ".venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info

REM Wait for backend
echo   Waiting for backend to start...
:wait_backend
timeout /t 2 /nobreak > nul
curl -s http://localhost:8000/api/health > nul 2>&1
if errorlevel 1 goto wait_backend
echo   Backend is ready!

REM Start frontend
echo [3/4] Starting Frontend (port 5173)...
cd /d "E:\Python_Code_Project\DataMind\frontend"
start "DataMind-Frontend" /B "node_modules\.bin\vite.cmd" --host 0.0.0.0 --port 5173

timeout /t 3 /nobreak > nul

REM Open browser
echo [4/4] Opening browser...
start http://localhost:5173

echo.
echo ========================================
echo   DataMind is running!
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:8000
echo   Login:    admin / admin123
echo ========================================
