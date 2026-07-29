@echo off
setlocal

set IMAGE_NAME=policy-summary
for /f "usebackq delims=" %%a in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"`) do set IMAGE_TAG=%%a
set FULL_TAG=%IMAGE_NAME%:%IMAGE_TAG%
set TAR_FILE=%IMAGE_NAME%-%IMAGE_TAG%.tar

cd /d "%~dp0.."

echo.
echo ============================================================
echo   %IMAGE_NAME% - Docker Build ^& Package
echo ============================================================

docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Desktop is not running.
    pause
    exit /b 1
)

echo [1/2] Building: %FULL_TAG%
docker build -t %FULL_TAG% .
if errorlevel 1 (
    echo [ERROR] docker build failed.
    pause
    exit /b 1
)
echo [OK] Build success

echo [2/2] Saving: docker\%TAR_FILE%
docker save -o docker\%TAR_FILE% %FULL_TAG%
if errorlevel 1 (
    echo [ERROR] docker save failed.
    pause
    exit /b 1
)

echo.
for %%A in (docker\%TAR_FILE%) do echo [OK] docker\%TAR_FILE%  (%%~zA bytes)
echo.
echo Upload to server:
echo   docker\%TAR_FILE%
echo   .env
echo   docker\deploy.sh
echo.
pause
endlocal
