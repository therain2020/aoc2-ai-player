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


def _latest_turn_summary():
    """(session_dir_name, rows, last_record) from the newest agent session turns.jsonl."""
    base = REPO / "sessions"
    if not base.exists():
        return None
    import json
    paths = sorted(base.glob("*agent*/turns.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not paths:
        return None
    p = paths[0]
    n = 0
    last = None
    try:
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                n += 1
                last = json.loads(line)
    except (OSError, json.JSONDecodeError):
        pass
    return (p.parent.name, n, last)


def show_status():
    agent_pids = _agent_pids()
    recorded = read_pid()
    alive = recorded and is_alive(recorded)
    print(f"  agent: recorded pid {recorded} | alive {'yes' if alive else 'no'} | "
          f"cmdline pids {agent_pids or '--'}")
    try:
        import json
        import urllib.request
        with urllib.request.urlopen(BRIDGE + "/state", timeout=2) as r:
            st = json.loads(r.read().decode())
        print(f"  bridge: online | T{st.get('turn')} {st.get('date', '')} | {st.get('turn_state')} "
              f"| in_game {st.get('in_game')} | 金{st.get('money')} 军{st.get('units')} "
              f"省{st.get('provinces')} 科技点{st.get('tech_points')} 外交点{st.get('diplomacy_points')}")
    except Exception as e:
        print(f"  bridge: offline ({e})")
    rec = _latest_turn_summary()
    if rec is None:
        print("  session: 尚无 agent 回合记录（turns.jsonl）")
    else:
        dn, rows, last = rec
        if last is None:
            print(f"  session: {dn} | turns.jsonl 空文件")
        else:
            from agent.actions import result_ok
            ok = sum(1 for r in (last.get("results") or []) if result_ok(r.get("result", "")))
            print(f"  session: {dn} | turns.jsonl {rows} 行 | 最新 T{last.get('turn')} "
                  f"type={last.get('type')} brief={str(last.get('brief'))[:40]} "
                  f"ok={ok}/{len(last.get('results') or [])}")
            if last.get("fail_reason"):
                print(f"  ⚠ 上次回合 FAIL: {last.get('fail_reason')}")
    root = (_config().get("game") or {}).get("root", "")
    if root:
        pause = Path(root) / "aoc2_pause.txt"
        strat = Path(root) / "aoc2_strategy.txt"
        strat_s = ""
        if strat.exists():
            try:
                strat_s = strat.read_text(encoding="utf-8").strip()[:120]
            except Exception:
                strat_s = "(读取失败)"
        print(f"  暂停(END): {'存在=已暂停' if pause.exists() else '无'} | 用户战略: {strat_s or '（无）'}")
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
