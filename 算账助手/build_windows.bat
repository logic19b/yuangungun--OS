@echo off
chcp 65001 >nul
echo ========================================
echo   算账助手 v8 - Windows 构建脚本
echo ========================================
echo.

:: 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装 Python 3.9+
    echo 下载: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 安装依赖
echo [1/4] 安装依赖...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

:: PyInstaller打包
echo [2/4] PyInstaller 打包中...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
pyinstaller suanshou.spec --noconfirm
if errorlevel 1 (
    echo [错误] 打包失败
    pause
    exit /b 1
)

:: 检查输出
if not exist "dist\算账助手\算账助手.exe" (
    echo [错误] 未找到打包输出: dist\算账助手\算账助手.exe
    pause
    exit /b 1
)

echo [3/4] 打包成功! 输出目录: dist\算账助手\
dir "dist\算账助手\算账助手.exe"

:: 检查Inno Setup
echo.
echo [4/4] 检查 Inno Setup...
where iscc >nul 2>&1
if errorlevel 1 (
    echo [提示] 未找到 Inno Setup (iscc)，跳过安装包生成
    echo 如需生成安装包，请安装 Inno Setup 6:
    echo   https://jrsoftware.org/isdl.php
    echo 安装后运行: iscc installer.iss
    echo.
    echo 当前可直接使用: dist\算账助手\算账助手.exe
    echo 或将 dist\算账助手\ 整个目录压缩为zip分发
) else (
    echo 正在生成安装包...
    iscc installer.iss
    if errorlevel 1 (
        echo [警告] 安装包生成失败，但exe已就绪
    ) else (
        echo 安装包已生成: installer_output\算账助手_v8_Setup.exe
    )
)

echo.
echo ========================================
echo   构建完成!
echo ========================================
pause
