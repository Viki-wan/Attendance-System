@echo off
REM Celery Worker Startup Script for Windows
REM Use --pool=solo for Windows compatibility

echo ========================================
echo Starting Celery Worker for Development
echo ========================================
echo.

REM Check if Redis is running
echo Checking Redis connection...
python -c "import redis; r = redis.Redis(host='127.0.0.1', port=6379); r.ping(); print('   OK: Redis is running')" 2>nul
if %errorlevel% neq 0 (
    echo    ERROR: Redis is not running!
    echo    Please start Redis in WSL2: sudo service redis-server start
    echo.
    pause
    exit /b 1
)
echo.

echo Starting Celery Worker...
echo Note: Using 'solo' pool for Windows compatibility
echo.
echo ========================================
echo.

REM Start Celery worker with solo pool (required for Windows)
REM Use python -m celery instead of celery command
python -m celery -A celery_worker.celery worker --loglevel=info --pool=solo

pause