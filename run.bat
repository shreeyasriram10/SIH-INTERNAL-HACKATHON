@echo off
setlocal
echo.
echo  ========================================================
echo   LOHA DRISHTI v2.3 - SAIL Maritime Decision Intelligence
echo   Smart India Hackathon (SIH) - Ministry of Steel
echo  ========================================================
echo.

cd /d "%~dp0"

REM Use the project virtualenv when one exists, otherwise the system Python.
if exist "backend\venv\Scripts\activate.bat" (
  call "backend\venv\Scripts\activate.bat"
  echo  [OK] Virtual environment activated.
) else if exist "venv\Scripts\activate.bat" (
  call "venv\Scripts\activate.bat"
  echo  [OK] Virtual environment activated.
) else (
  echo  [i] No venv found - using the system Python.
)

python -c "import fastapi" 2>nul
if errorlevel 1 (
  echo  [!] Dependencies missing. Installing from requirements.txt...
  python -m pip install -r requirements.txt || goto :failed
)

if not exist "backend\ml\model.pkl" (
  echo  [i] No model artifact found - training one now...
  python backend\ml\train.py || goto :failed
)

echo.
echo   Main Platform:  http://localhost:8000
echo   Sign In Page:   http://localhost:8000/login
echo   ML Training:    http://localhost:8000/ml-training
echo   Verification:   http://localhost:8000/verification
echo   API Swagger:    http://localhost:8000/docs
echo.
echo   Demo sign-in:   admin@sail.gov.in / 12345
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --app-dir backend
goto :eof

:failed
echo.
echo  [X] Startup failed. See the error above.
exit /b 1
