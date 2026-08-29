"""AoC2 Agent 控制面板（手动启动/停止/状态）。

Usage: python agent/panel.py
"""
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PID_FILE = REPO / "agent.pid"
LOG_FILE = REPO / "logs" / "agent.log"
BRIDGE = "http://127.0.0.1:7187"   # EngineGateway (T014); legacy 9110 retired
BRIDGE_PORT = 7187


def _now():
    return time.strftime("%H:%M:%S")


def read_pid():
    try:
        return int(PID_FILE.read_text().strip())
    except Exception:
        return None


def is_alive(pid=None) -> bool:
    pid = pid or read_pid()
    if not pid:
        return False
    try:
        import urllib.request
        with urllib.request.urlopen(BRIDGE + "/ping", timeout=1):
            pass
    except Exception:
        pass
    out = subprocess.run(["tasklist", "/fi", f"pid eq {pid}"],
                         capture_output=True, text=True, shell=True)
    return "python.exe" in out.stdout.lower()


def start_agent():
    pid = read_pid()
    if pid and is_alive(pid):
        print(f"  Agent already running (pid {pid})")
        return
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log_f = open(LOG_FILE, "w", encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-X", "utf8", "-m", "agent.main", "--max-plans", "0"],
        cwd=str(REPO), env=env, stdout=log_f, stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    PID_FILE.write_text(str(proc.pid))
    print(f"  Agent started (pid {proc.pid}), log: logs/agent.log")
    for _ in range(20):
        try:
            import urllib.request
            with urllib.request.urlopen(BRIDGE + "/state", timeout=1) as r:
                import json
                st = json.loads(r.read().decode())
                print(f"  bridge OK: turn={st.get('turn')} in_game={st.get('in_game')}")
                return
        except Exception:
            time.sleep(0.5)
    print("  waiting for bridge... (start game & load a save first)")


def stop_agent():
    pid = read_pid()
    if not pid:
        print("  no pid record (falling back to commandline scan)")
    cleaned = 0
    for p in _agent_pids():
        subprocess.run(["taskkill", "/PID", str(p), "/F", "/T"],
                       capture_output=True, shell=True)
        cleaned += 1
    if PID_FILE.exists():
        PID_FILE.unlink()
    print(f"  stopped {cleaned} agent process(es)")


def _agent_pids():
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | "
         "Where-Object { $_.CommandLine -match 'agent.main' } | "
         "ForEach-Object { $_.ProcessId }"],
        capture_output=True, text=True, shell=True)
    pids = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids


def start_game():
    """Start the game with the EngineGateway bridge (T011 boot-agent mode)."""
    import yaml
    cfg_path = REPO / "config.yaml"
    if not cfg_path.exists():
        print("  config.yaml missing - copy config.yaml.template, set game.root")
        return
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    root = (cfg.get("game") or {}).get("root")
    if not root:
        print("  config game.root not set")
        return
    ps1 = REPO / "game_bridge" / "start_game.ps1"
    proc = subprocess.Popen(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1), str(root)],
        cwd=str(REPO))
    print(f"  game launched (pid {proc.pid}), bridge should come up at {BRIDGE}")


def show_status():
    pid = read_pid()
    alive = pid and is_alive(pid)
    print(f"  recorded pid: {pid}   process alive: {'yes' if alive else 'no'}")
    try:
        import json
        import urllib.request
        with urllib.request.urlopen(BRIDGE + "/state", timeout=2) as r:
            st = json.loads(r.read().decode())
        print(f"  bridge: online | turn {st.get('turn')} | state {st.get('turn_state')} "
              f"| in_game {st.get('in_game')} | money {st.get('money')} units {st.get('units')}")
    except Exception as e:
        print(f"  bridge: offline ({e})")
    log_size = LOG_FILE.stat().st_size if LOG_FILE.exists() else 0
    print(f"  log size: {log_size} bytes")


def main():
    if os.name == "nt":
        os.system("chcp 65001 > nul")
    print("=== AoC2 Agent Control Panel ===")
    while True:
        print("\n1) Start agent   2) Stop agent   3) Status   4) Start game (gateway)   0) Exit")
        try:
            choice = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if choice == "1":
            start_agent()
        elif choice == "2":
            stop_agent()
        elif choice == "3":
            show_status()
        elif choice == "4":
            start_game()
        elif choice == "0":
            break
        else:
            print("  invalid input")
    print("panel exited")


if __name__ == "__main__":
    main()
