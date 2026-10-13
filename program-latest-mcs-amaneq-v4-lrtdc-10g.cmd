@echo off
setlocal
rem Download and program the latest official lrtdc-10g MCS for AMANEQ v4.
set "AMANEQ_EXTRA_ARGS=%*"
call "%~dp0firmware-latest-amaneq-common.cmd" amaneq-v4 lrtdc-10g mcs
exit /b %errorlevel%
