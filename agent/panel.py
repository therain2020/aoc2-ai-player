"""AoC2 Agent 控制面板（手动启动/停止/状态）。

Usage: python agent/panel.py
"""
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))   # panel runs via `python agent/panel.py` -> cwd of script is agent/

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


def bridge_ready() -> bool:
    """T044: bridge readiness probe before Start (gateway.jar injected?)."""
    try:
        import urllib.request
        with urllib.request.urlopen(BRIDGE + "/ping", timeout=1) as r:
            return r.read().decode("utf-8").strip() == "pong"
    except Exception:
        return False


def is_alive(pid=None) -> bool:
    pid = pid or read_pid()
    if not pid:
        return False
    out = subprocess.run(["tasklist", "/fi", f"pid eq {pid}"],
                         capture_output=True, text=True, shell=True)
    return "python.exe" in out.stdout.lower()


def start_agent():
    # T044: double-match (pid file + commandline) before starting
    dup = _agent_pids()
    if read_pid() and is_alive(read_pid()):
        print(f"  Agent already running (pid {read_pid()})")
        return
    if dup:
        print(f"  stale agent process found via commandline ({dup}) - stop it first")
        return
    if not bridge_ready():
        print("  bridge NOT ready (game not started / gateway.jar not injected)")
        ans = input("  start agent anyway? (y/n) > ").strip().lower()
        if ans not in ("y", "yes"):
            return
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log_f = open(LOG_FILE, "w", encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-u", "-X", "utf8", "-m", "agent.main", "--max-plans", "0"],
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


def _gateway_pids():
    """Java/Javaw processes carrying the gateway javaagent (T044: stop together)."""
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"name='java.exe' or name='javaw.exe'\" | "
         "Where-Object { $_.CommandLine -match 'gateway.jar' } | "
         "ForEach-Object { $_.ProcessId }"],
        capture_output=True, text=True, shell=True)
    pids = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids


def stop_agent():
    """Stop the Agent python processes ONLY — the game window stays untouched."""
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
    print(f"  stopped {cleaned} agent process(es) — 游戏进程保留")


def stop_game():
    """Kill the game process carrying the gateway (menu 5, explicit confirm)."""
    pids = _gateway_pids()
    if not pids:
        print("  no game/gateway process found")
        return
    ans = input(f"  关闭网关 = 关闭游戏进程 {pids}（未保存进度会丢失），确认? (y/n) > ").strip().lower()
    if ans not in ("y", "yes"):
        print("  cancelled")
        return
    for p in pids:
        subprocess.run(["taskkill", "/PID", str(p), "/F", "/T"],
                       capture_output=True, shell=True)
    print(f"  stopped game (gateway) process(es): {pids}")


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


def _config():
    import yaml
    cfg_path = REPO / "config.yaml"
    if not cfg_path.exists():
        return {}
    try:
        return yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def show_status():
    """Unified status area (agent/status.snapshot): alive / bridge / session /
    pause source / gear — no guessing."""
    from agent import status as st_mod
    from agent.mechanics.gears import GEAR_TEXT
    snap = st_mod.snapshot(_config())
    a = snap["agent"]
    b = snap["bridge"]
    s = snap["session"]
    p = snap["pause"]
    sg = snap["strategy"]
    print(f"  agent: running={a['running']} | pids={a['pids'] or '--'} | pid_record={a['pid_record']}")
    if b:
        print(f"  bridge: online | T{b.get('turn')} {b.get('date', '')} | {b.get('turn_state')} "
              f"| in_game {b.get('in_game')} | 金{b.get('money')} 军{b.get('units')} 省{b.get('provinces')}")
    else:
        print("  bridge: offline")
    if s:
        print(f"  session: {s['name']} | turns.jsonl {s['rows']} 行 | 最新 T{s.get('turn')} "
              f"{s.get('type') or ''} {s.get('brief') or ''}")
    else:
        print("  session: --")
    if p["paused"]:
        print(f"  pause: 已暂停（来源 {p['by']} @ {p['ts']}）— 恢复=删除暂停文件")
    else:
        print("  pause: 否")
    if sg.get("gear"):
        print(f"  strategy gear: {GEAR_TEXT[sg['gear'] - 1]}")
    print(f"  log: logs/agent.log {LOG_FILE.stat().st_size if LOG_FILE.exists() else 0} bytes")


def main():
    if os.name == "nt":
        os.system("chcp 65001 > nul")
    print("=== AoC2 Agent Control Panel ===")
    while True:
        print("\n1) Start agent   2) Stop agent   3) Status   4) Start game (gateway)"
              "   5) Stop game   0) Exit")
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
        elif choice == "5":
            stop_game()
        elif choice == "0":
            break
        else:
            print("  invalid input")
    print("panel exited")


if __name__ == "__main__":
    main()
