@echo off
echo.
echo  ========================================================
echo   LOHA DRISHTI v2.2 — SAIL Maritime Decision Intelligence
echo   Smart India Hackathon (SIH) - Ministry of Steel
echo  ========================================================
echo.
echo  Starting server...
echo.
cd /d "%~dp0backend"
call venv\Scripts\activate
echo  [OK] Python environment activated.
echo.
echo  Main Platform:  http://localhost:8000
echo  Sign In Page:   http://localhost:8000/login
echo  ML Training:    http://localhost:8000/ml-training
echo  Verification:   http://localhost:8000/verification
echo  API Swagger:    http://localhost:8000/docs
echo.
echo  Sample Credentials: admin@sail.gov.in / 12345
echo.
uvicorn main:app --host 0.0.0.0 --port 8000
