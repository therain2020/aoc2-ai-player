@echo off
rem ASCII-only proxy: launches the EngineGateway game start for Chinese paths.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_game.ps1" %*
exit /b %errorlevel%
