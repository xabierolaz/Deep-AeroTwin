@echo off
setlocal
if not defined PORCE_OBSTACLE_TOKEN_PERSIST set "PORCE_OBSTACLE_TOKEN_PERSIST=0"
call "%~dp0tools\launch_workflow.bat" SIMULATION
exit /b %errorlevel%
