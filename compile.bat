@echo off
chcp 65001 >nul 2>&1  :: Switch to UTF-8 encoding
setlocal enabledelayedexpansion

:: Configuration parameters
set "VENV_DIR=.venv"                  :: Virtual environment directory
set "SCRIPT_NAME=main.py"            :: Main script file
set "OUTPUT_DIR=output"              :: Output directory
set "ICON_PATH=res/ico/favicon.ico"  :: Icon file path
set "DATA_FILES=res/ico/*.ico=res/ico/"  :: Data files mapping
set "UPX_PATH=D:\upx-5.0.2-win64\upx.exe" ::若UPX在环境变量中，直接用"upx"；否则填完整路径如"tools/upx.exe"
:: 1. Check if virtual environment exists
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo Error: Virtual environment not found at "%VENV_DIR%"
    echo Tip: Create it first with command: python -m venv "%VENV_DIR%"
    exit /b 1
)

:: 2. Check if main script exists
if not exist "%SCRIPT_NAME%" (
    echo Error: Main script "%SCRIPT_NAME%" not found
    exit /b 1
)

:: 3. Check if Nuitka is installed in venv
if not exist "%VENV_DIR%\Scripts\nuitka.cmd" (
    echo Error: Nuitka not installed in virtual environment
    echo Tip: Install it with: "%VENV_DIR%\Scripts\pip" install --upgrade nuitka
    exit /b 1
)

:: 4. Check if icon file exists
set "ICON_PARAM="
if exist "%ICON_PATH%" (
    set "ICON_PARAM=--windows-icon-from-ico="%ICON_PATH%""
) else (
    echo Warning: Icon file "%ICON_PATH%" not found, using default icon
)

:: 5. Activate venv and compile with Nuitka
echo Activating virtual environment: "%VENV_DIR%"...
call "%VENV_DIR%\Scripts\activate.bat"

echo Starting Nuitka compilation for "%SCRIPT_NAME%"...
"%VENV_DIR%\Scripts\nuitka" ^
    --lto=no ^
    --jobs=5 ^
    --onefile ^
    --mingw64 ^
    --standalone ^
    --output-dir="%OUTPUT_DIR%" ^
    --windows-console-mode=disable ^
    !ICON_PARAM! ^
    !UPX_PARAM! ^
    --enable-plugin=pyside6 ^
    --include-qt-plugins=sensible,styles ^
    --include-data-files="%DATA_FILES%" ^
    --windows-disable-console ^
    --follow-imports ^
    --show-progress ^
    --show-memory ^
    "%SCRIPT_NAME%"

:: 6. Check compilation result
if exist "%OUTPUT_DIR%\%SCRIPT_NAME:.py=.exe%" (
    echo Compilation successful! EXE path: "%OUTPUT_DIR%"
    pause
) else (
    echo Compilation failed! Check error messages above.
    pause
    exit /b 1
)

:: 7. Deactivate venv
deactivate
endlocal
