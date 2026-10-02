@echo off
setlocal
cd /d "%~dp0"
title JobHunt
rem "run.bat --auto" is how Windows Task Scheduler starts the daily auto-search (Settings tab). It runs in a
rem minimised window, searches, shows a notification, then closes by itself.
set "AUTO="
if /i "%~1"=="--auto" set "AUTO=1"
if defined AUTO if /i not "%~2"=="min" (
    start "JobHunt daily search" /min "%~f0" --auto min
    exit /b
)
set "PY=.venv\Scripts\python.exe"
set "PACKAGES=fastapi, uvicorn, requests, jobspy, playwright, openpyxl, defusedxml, pypdf, anthropic"

rem ---- 1. Is the app's Python environment usable on THIS computer? ----
rem A .venv copied from another computer points at that computer's Python install and fails here,
rem so it is rebuilt. This is what makes a plain copy-and-paste of the JobHunt folder work.
if not exist "%PY%" goto :build_env
"%PY%" -c "import sys" >nul 2>&1
if not errorlevel 1 goto :check_packages
echo The Python environment in this folder was made on another computer or is damaged.
echo Rebuilding it for this computer...

:build_env
call :find_python
if errorlevel 1 call :install_python
if errorlevel 1 goto :no_python
if exist ".venv" rmdir /s /q ".venv"
if exist ".venv" (
    echo Could not remove the old .venv folder. Close any other JobHunt window and try again.
    goto :error
)
echo Creating Python environment...
%BASE% -m venv .venv
if errorlevel 1 goto :error

rem ---- 2. Are all packages installed and importable? ----
:check_packages
rem A changed constraints.txt (for example a security update) installs the new versions once.
fc /b constraints.txt ".venv\installed-constraints.txt" >nul 2>&1
if errorlevel 1 goto :install_packages
"%PY%" -c "import %PACKAGES%" >nul 2>&1
if not errorlevel 1 goto :start
:install_packages
echo Installing packages, this takes a few minutes the first time...
"%PY%" -m pip install --upgrade pip
rem constraints.txt: the exact, tested and vulnerability-scanned version of every package
"%PY%" -m pip install -r requirements.txt -c constraints.txt
if errorlevel 1 goto :error
rem --no-deps: JobSpy pins an old numpy that cannot install on new Python versions
"%PY%" -m pip install --no-deps -c constraints.txt python-jobspy==1.1.82
if errorlevel 1 goto :error
"%PY%" -c "import %PACKAGES%"
if errorlevel 1 goto :error
copy /y constraints.txt ".venv\installed-constraints.txt" >nul

rem ---- 3. Start the app ----
:start
if defined AUTO goto :auto
if not exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" if not exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" echo Note: Microsoft Edge was not found, so Naukri searches will not work on this computer.
echo.
echo JobHunt is running at http://localhost:8000
echo Keep this window open while you use the app. Close it to stop.
echo.
start "" cmd /c "timeout /t 3 >nul & start http://localhost:8000"
"%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
goto :eof

rem Daily auto-search: if JobHunt is already open, ask it to search; otherwise start it just for the search.
:auto
"%PY%" -c "import socket, sys; s = socket.socket(); s.settimeout(2); sys.exit(0 if s.connect_ex(('127.0.0.1', 8000)) == 0 else 1)"
if not errorlevel 1 (
    "%PY%" -c "import urllib.request as u; u.urlopen(u.Request('http://127.0.0.1:8000/api/autosearch/run', data=b'{}', method='POST', headers={'X-JobHunt': '1', 'Content-Type': 'application/json'}), timeout=30)"
    exit /b
)
echo JobHunt daily auto-search is running. This window closes by itself when it finishes.
set "JOBHUNT_AUTORUN=1"
"%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
exit /b

rem Finds Python 3.12+ on this computer: "python" on PATH first, then the "py" launcher.
rem (The tested package versions in constraints.txt need 3.12 or newer.)
:find_python
set "BASE="
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "BASE=python"
    exit /b 0
)
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "BASE=py -3"
    exit /b 0
)
exit /b 1

rem No usable Python: installs Python 3.14 for this Windows user with winget, which comes with Windows 10 and 11.
rem No administrator rights are needed.
:install_python
where winget >nul 2>&1
if errorlevel 1 (
    echo Python 3.12 or newer was not found, and winget is not available to install it automatically.
    exit /b 1
)
echo.
echo Python 3.12 or newer was not found on this computer.
echo Installing Python 3.14 with winget. This takes a few minutes and needs internet...
call winget install --id Python.Python.3.14 --exact --source winget --scope user --silent --accept-package-agreements --accept-source-agreements
rem This window's PATH doesn't include the new Python yet, so look where the installer puts it.
for %%d in ("%LOCALAPPDATA%\Programs\Python\Python314" "%ProgramFiles%\Python314") do (
    if exist "%%~d\python.exe" (
        set "BASE="%%~d\python.exe""
        echo Python 3.14 is installed.
        exit /b 0
    )
)
call :find_python
if not errorlevel 1 exit /b 0
echo winget could not install Python.
exit /b 1

:no_python
echo.
echo JobHunt needs Python 3.12 or newer, and it could not be installed automatically.
echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH" during setup,
echo then double-click run.bat again.
pause
exit /b 1

:error
echo.
echo Setup failed. Read the messages above.
pause
exit /b 1
