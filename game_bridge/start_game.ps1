# Start AoC2 with the source-level bridge (EngineGateway).
# Usage: powershell -File start_game.ps1 [game root]
# No arg -> default root below. Modes: $env:LEGACY_AGENT=1 (old ASM), $env:ENGINE_GATEWAY_CP=1 (no auto-start).
$ErrorActionPreference = "Stop"

$defaultRoot = "$HOME\Downloads\Age of History II（含汉化）\Age of History II"

$root = $args[0]
if (-not $root) { $root = $defaultRoot }
if (-not (Test-Path (Join-Path $root "AoC2.exe"))) {
    Write-Host "[EngineGateway] game root not found: $root"
    exit 1
}
$repo = Split-Path (Split-Path $MyInvocation.MyCommand.Path -Parent) -Parent
$gatewayJar = Join-Path $repo "game_bridge\engine_gateway\gateway.jar"
$legacyJar = Join-Path $repo "game_bridge\agent_bridge\agent-bridge.jar"
$jreJavaw = Join-Path $root "jre\bin\javaw.exe"
$main = "age.of.civilizations2.jakowski.lukasz.desktop.DesktopLauncher"

function Launch($argsLine) {
    # libGDX desktop internal files (window icon etc.) resolve against the game
    # working directory -- always start with cwd = game root.
    Start-Process -FilePath $jreJavaw -ArgumentList $argsLine -WorkingDirectory $root
}

if ($env:LEGACY_AGENT -eq "1") {
    Write-Host "[EngineGateway] LEGACY ASM mode"
    Launch @("-javaagent:`"$legacyJar`"", "-jar", "AoC2.exe")
    exit 0
}
if ($env:ENGINE_GATEWAY_CP -eq "1") {
    Write-Host "[EngineGateway] classpath mode - no auto-start, debug only"
    $cp = (Join-Path $root "AoC2.exe") + ";" + $gatewayJar
    Launch @("-cp:" + $cp, $main)
    exit 0
}

Write-Host "[EngineGateway] boot-agent mode"
Launch @("-javaagent:`"$gatewayJar`"", "-jar", "AoC2.exe")
exit 0
