@echo off
setlocal
rem Download and program the latest official skeleton BIT for amaneq-v4.
set "AMANEQ_EXTRA_ARGS=%*"
call "%~dp0firmware-latest-amaneq-common.cmd" amaneq-v4 skeleton bit
exit /b %errorlevel%
