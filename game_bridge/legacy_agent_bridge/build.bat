@echo off
rem Build AgentBridge agent jar (agent-bridge.jar) with ASM shaded in.
rem Requires: aoc2.jar extracted at repo\.bridge\aoc2.jar (run game_bridge\extract_jar.py first)
cd /d %~dp0
set BRIDGE=%CD%
set REPO=%BRIDGE%\..\..
set AOC2JAR=%REPO%\.bridge\aoc2.jar
if not exist "%AOC2JAR%" (
  echo [ERROR] %AOC2JAR% missing - run: python game_bridge\extract_jar.py <AoC2.exe> ...
  exit /b 1
)
if not exist build mkdir build
javac -source 8 -target 8 -Xlint:-options -encoding utf-8 -cp "lib\asm-9.7.1.jar;%AOC2JAR%" -d build src\age\of\civilizations2\jakowski\lukasz\AgentBridge.java src\agentbridge\Launcher.java
if errorlevel 1 (
  echo BUILD FAILED
  exit /b 1
)
rem merge ASM classes into build dir, then package agent jar
cd /d build
jar xf ..\lib\asm-9.7.1.jar org
echo Premain-Class: agentbridge.Launcher > manifest.mf
echo. >> manifest.mf
jar --create --file ..\agent-bridge.jar --manifest manifest.mf -C . .
cd /d %BRIDGE%
echo BUILD OK: agent-bridge.jar
