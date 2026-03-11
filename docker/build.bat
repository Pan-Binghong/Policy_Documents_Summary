@echo off
cd /d %~dp0\..

echo [1/2] Building Docker image...
docker build -t policy-summary:20260311 .
if %errorlevel% neq 0 (
    echo Build failed
    exit /b 1
)

echo [2/2] Exporting to tar...
docker save policy-summary:20260311 -o docker\policy-summary.tar
if %errorlevel% neq 0 (
    echo Export failed
    exit /b 1
)

echo Done: docker\policy-summary.tar
