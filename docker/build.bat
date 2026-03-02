@echo off
cd /d %~dp0\..

echo [1/2] 构建 Docker 镜像...
docker build -t policy-summary:20260302 .
if %errorlevel% neq 0 (
    echo 构建失败
    exit /b 1
)

echo [2/2] 导出为 tar 包...
docker save policy-summary:20260302 -o docker\policy-summary.tar
if %errorlevel% neq 0 (
    echo 导出失败
    exit /b 1
)

echo 完成：docker\policy-summary.tar
