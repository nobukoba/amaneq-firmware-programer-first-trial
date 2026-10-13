@echo off
setlocal
if "%~3"=="" (
  echo ERROR: Target, firmware family, and format are required. 1>&2
  exit /b 2
)
set "AMANEQ_TARGET=%~1"
set "AMANEQ_FAMILY=%~2"
set "AMANEQ_FORMAT=%~3"
rem Set AMANEQ_PYTHON to an executable path to override Python discovery.
rem Configure cygpath through PATH, AMANEQ_CYGPATH_DIR, or --cygpath-dir.
if defined AMANEQ_PYTHON (
  "%AMANEQ_PYTHON%" "%~dp0amaneq-firmware-programer.py" program %AMANEQ_EXTRA_ARGS% --latest --firmware %AMANEQ_FAMILY% --target %AMANEQ_TARGET% --format %AMANEQ_FORMAT% --yes
  exit /b
)
where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%~dp0amaneq-firmware-programer.py" program %AMANEQ_EXTRA_ARGS% --latest --firmware %AMANEQ_FAMILY% --target %AMANEQ_TARGET% --format %AMANEQ_FORMAT% --yes
  exit /b
)
python "%~dp0amaneq-firmware-programer.py" program %AMANEQ_EXTRA_ARGS% --latest --firmware %AMANEQ_FAMILY% --target %AMANEQ_TARGET% --format %AMANEQ_FORMAT% --yes
exit /b %errorlevel%
