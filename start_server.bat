@echo off
REM SimpleAgent Web Server 启动脚本 (Windows)
REM Usage: start_server.bat [port]

setlocal enabledelayedexpansion

REM 设置默认参数
set HOST=127.0.0.1
set PORT=8000
set RELOAD=

REM 解析命令行参数
if "%1"=="--help" goto :help
if "%1"=="-h" goto :help
if not "%1"=="" set PORT=%1
if "%2"=="--reload" set RELOAD=--reload
if "%2"=="-r" set RELOAD=--reload

echo 🚀 SimpleAgent Web Server 启动脚本
echo ==================================

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

echo ✅ Python 环境检查通过

REM 检查配置文件
if not exist "config\provider.json" (
    echo ⚠️  配置文件不存在
    echo ℹ️  正在复制配置模板...
    
    if exist "config\provider_template.json" (
        copy "config\provider_template.json" "config\provider.json" >nul
        echo ✅ 配置模板已复制
        echo ⚠️  请编辑 config\provider.json 填入您的API密钥
        echo ℹ️  示例: notepad config\provider.json
        echo.
        echo ℹ️  继续启动服务器 ^(您可以稍后修改配置^)...
    ) else (
        echo ❌ 配置模板文件不存在，请检查项目结构
        pause
        exit /b 1
    )
) else (
    echo ✅ 配置文件检查通过
)

REM 启动服务器
echo ✅ 正在启动 SimpleAgent Web Server...
echo 📍 地址: http://%HOST%:%PORT%
echo 📖 API文档: http://%HOST%:%PORT%/docs
echo 🔗 健康检查: http://%HOST%:%PORT%/health
echo 💡 按 Ctrl+C 停止服务器
echo ==================================

REM 启动命令
python start_web_server.py --host %HOST% --port %PORT% %RELOAD%

goto :end

:help
echo SimpleAgent Web Server 启动脚本 (Windows)
echo.
echo 用法:
echo     start_server.bat [端口号] [选项]
echo.
echo 选项:
echo     --help, -h      显示此帮助信息
echo     --reload, -r    启用开发模式 (文件修改后自动重载)
echo.
echo 示例:
echo     start_server.bat                # 默认启动 (端口8000)
echo     start_server.bat 8080           # 在8080端口启动
echo     start_server.bat 8000 --reload  # 开发模式启动
echo.
pause
exit /b 0

:end
pause
