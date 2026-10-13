@echo off
setlocal
rem Download and program the latest official mikumari MCS for AMANEQ v4.
set "AMANEQ_EXTRA_ARGS=%*"
call "%~dp0firmware-latest-amaneq-common.cmd" amaneq-v4 mikumari mcs
exit /b %errorlevel%
