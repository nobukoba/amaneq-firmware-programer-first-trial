@echo off
setlocal
rem Download and program the latest official HR-TDC mezzanine MCS.
rem Detect MT25QU256/N25Q128 automatically before selecting the download.
set "AMANEQ_EXTRA_ARGS=%*"
call "%~dp0firmware-latest-amaneq-common.cmd" hrtdc-mezzanine hrtdc mcs
exit /b %errorlevel%
