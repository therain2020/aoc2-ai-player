@echo off
rem Start AoC2 with AgentBridge injected (uses repo agent-bridge.jar).
rem Usage: start_game.bat "<game root>"  e.g. start_game.bat "D:\Games\Age of History II"
set ROOT=%1
if "%ROOT%"=="" (
  echo usage: start_game.bat ^<game root^>
  exit /b 1
)
set REPO=%~dp0..
"%ROOT%\jre\bin\javaw.exe" -javaagent:"%REPO%\game_bridge\agent_bridge\agent-bridge.jar" -jar "%ROOT%\AoC2.exe"
