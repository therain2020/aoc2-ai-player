@echo off
rem Build SaveDump for Java 8 (run with any JDK >= 9 supporting --release)
cd /d %~dp0
if not exist build mkdir build
javac --release 8 -d build SaveDump.java
if errorlevel 1 (
  echo BUILD FAILED
  exit /b 1
)
echo BUILD OK: game_bridge\build\SaveDump.class
