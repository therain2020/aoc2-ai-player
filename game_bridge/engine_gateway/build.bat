@echo off
rem Build EngineGateway (source-level bridge, Java 8 bytecode) -> gateway.jar
rem Requires: aoc2.jar at repo\.bridge\aoc2.jar (run game_bridge\extract_jar.py first)
cd /d %~dp0
set GW=%CD%
set REPO=%GW%\..\..
set AOC2JAR=%REPO%\.bridge\aoc2.jar
if not exist "%AOC2JAR%" (
  echo [ERROR] %AOC2JAR% missing - run: python game_bridge\extract_jar.py ^<AoC2.exe^> ...
  exit /b 1
)
if not exist build mkdir build
javac --release 8 -Xlint:-options -nowarn -encoding utf-8 -cp "%AOC2JAR%" -d build src\agentbridge\gateway\EngineApi.java src\agentbridge\gateway\Json.java src\agentbridge\gateway\EngineActions.java src\agentbridge\gateway\EngineState.java src\agentbridge\gateway\BridgeHttpServer.java src\agentbridge\gateway\EngineGateway.java src\agentbridge\gateway\GatewayPremain.java
if errorlevel 1 (
  echo BUILD FAILED
  exit /b 1
)
echo Premain-Class: agentbridge.gateway.GatewayPremain > manifest.mf
echo. >> manifest.mf
jar --create --file gateway.jar --manifest manifest.mf -C build .
echo BUILD OK: gateway.jar
