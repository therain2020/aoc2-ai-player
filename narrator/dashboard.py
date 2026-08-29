"""AoC2 AI 上帝视角控制台：指挥（战略文本/六档/暂停）+ 监控（≤2s 轮询、决策流、
资源曲线、余额）+ 计划面板。

数据流（dashboard-api.md）：只读桥 GET /state、GET /plan；写文件通道
（aoc2_strategy.txt / aoc2_pause.txt 于游戏根目录）；/action 由 Agent 主循环执行。

Usage: python -m narrator.dashboard [--port 8080] [--session <dir>]
"""
import argparse
import json
import sys
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent.mechanics.gears import GEAR_TEXT  # noqa: E402
# T014: 桥端口统一 7187（旧 9110 已退役）
BRIDGE = "http://127.0.0.1:7187"

# 六档战略（单一来源：agent/mechanics/gears.py GEAR_TEXT）
GEARS = GEAR_TEXT

# ---- bridge /state TTL 2s cache ----
_state_cache = {"ts": 0.0, "body": {}}


def fetch_bridge(path: str, timeout: float = 4.0) -> dict:
    try:
        with urllib.request.urlopen(BRIDGE + path, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return {}


def fetch_state_cached() -> dict:
    now = time.time()
    if now - _state_cache["ts"] >= 2.0:
        st = fetch_bridge("/state")
        if st:
            _state_cache["body"] = st
            _state_cache["ts"] = now
    return _state_cache["body"]


def load_turns(session_dir: Path) -> list:
    path = session_dir / "turns.jsonl"
    if not path.exists():
        return []
    turns = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                turns.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return turns


def history_for_curve(turns: list) -> list:
    out = []
    for t in turns[-40:]:
        st = t.get("state") or {}
        ledger = t.get("ledger") or {}
        out.append({
            "turn": t.get("turn"),
            "money": st.get("money"),
            "diplo_pts": ledger.get("diplo_pts"),
            "mechanic_phase": t.get("mechanic_phase"),
        })
    return out


def game_root() -> Path:
    try:
        import yaml
        cfg_path = REPO / "config.yaml"
        if cfg_path.exists():
            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            root = (cfg.get("game") or {}).get("root")
            if root:
                return Path(root)
    except Exception:
        pass
    return REPO


def read_strategy_file() -> str:
    p = game_root() / "aoc2_strategy.txt"
    try:
        if p.exists():
            return p.read_text(encoding="utf-8").strip()[:500]
    except OSError:
        pass
    return ""


def pause_meta() -> dict:
    """(exists, by, ts) — pause file metadata (first line marker)."""
    p = game_root() / "aoc2_pause.txt"
    if not p.exists():
        return {"paused": False, "pause_by": None, "pause_ts": None}
    by, ts = None, None
    try:
        first = p.read_text(encoding="utf-8", errors="replace").splitlines()[0]
        if first.startswith("#"):
            parts = first.lstrip("#").split(" ", 1)
            by = parts[0]
            ts = parts[1] if len(parts) > 1 else None
    except OSError:
        pass
    return {"paused": True, "pause_by": by or "unknown", "pause_ts": ts}


def is_paused() -> bool:
    return (game_root() / "aoc2_pause.txt").exists()


def apply_gear(value) -> bool:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return False
    if not 1 <= n <= 6:
        return False
    (game_root() / "aoc2_strategy.txt").write_text(GEARS[n - 1], encoding="utf-8")
    return True


def apply_strategy_text(value) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or len(text) > 500:
        return False
    (game_root() / "aoc2_strategy.txt").write_text(text, encoding="utf-8")
    return True


def apply_pause(value) -> bool:
    p = game_root() / "aoc2_pause.txt"
    import datetime
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    if value is True or (isinstance(value, str) and value.lower() in ("1", "true", "yes")):
        p.write_text(f"#user:dashboard {stamp}\npaused", encoding="utf-8")
        return True
    if value is False or (isinstance(value, str) and value.lower() in ("0", "false", "no")):
        if p.exists():
            p.unlink()
        return True
    if isinstance(value, str) and value.lower() == "toggle":
        if p.exists():
            p.unlink()
        else:
            p.write_text(f"#user:dashboard {stamp}\npaused", encoding="utf-8")
        return True
    return False


PAGE = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>AoC2 AI 上帝视角控制台</title>
<style>
 body{font-family:"Microsoft YaHei",sans-serif;background:#0f1218;color:#dde2ea;margin:0;padding:20px;max-width:1040px;margin:0 auto}
 h1{font-size:18px;color:#f2c14e;margin:0 0 4px}
 .sub{color:#7c8698;font-size:12px;margin-bottom:14px}
 .grid{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}
 .stat{background:#1a2029;border:1px solid #2a3342;border-radius:10px;padding:10px 14px;min-width:100px}
 .stat .k{color:#7c8698;font-size:11px}
 .stat .v{color:#e8ecf2;font-size:19px;font-weight:700;margin-top:2px}
 .stat .v.small{font-size:14px}
 .col{display:flex;gap:16px;flex-wrap:wrap}
 .col>div{flex:1 1 480px;min-width:320px}
 .card{background:#1a2029;border:1px solid #2a3342;border-radius:10px;padding:12px 16px;margin-bottom:12px}
 .head{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap;margin-bottom:6px}
 .turn{font-weight:700;color:#f2c14e}
 .ts{color:#7c8698;font-size:11px}
 .brief{font-size:14px;line-height:1.6;margin-bottom:8px}
 .chip{display:inline-block;background:#243044;border:1px solid #34435c;color:#b8c7dd;border-radius:6px;padding:2px 8px;margin:2px 4px 2px 0;font-size:11px}
 .res{display:inline-block;border-radius:6px;padding:2px 8px;margin:2px 4px 2px 0;font-size:10px}
 .res.ok{background:#16301f;color:#7fd99a;border:1px solid #27573a}
 .res.fail{background:#351c1c;color:#f0a1a1;border:1px solid #6b3434}
 .tok{color:#8fa3c4;font-size:11px;margin-top:6px}
 /* 指挥面板 */
 .cmdgrid{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:end;margin-bottom:8px}
 textarea,select,button,input{font-family:inherit;font-size:13px;border-radius:8px;border:1px solid #34435c;background:#141b24;color:#e8ecf2;padding:8px 10px}
 textarea{width:100%;resize:vertical;min-height:64px}
 button{background:#f2c14e;color:#141410;font-weight:700;border:none;padding:8px 16px;cursor:pointer}
 button.dim{background:#243044;color:#b8c7dd}
 .gearbtn{padding:5px 9px;font-size:12px;margin:2px 4px 2px 0;background:#243044;color:#b8c7dd;border:1px solid #34435c}
 .gearbtn.on{background:#f2c14e;color:#141410}
 .planline{color:#9db4d0;font-size:12px;line-height:1.5}
 .planbar{display:flex;gap:6px;overflow-x:auto;padding:6px 0}
 .turnchip{flex:1 1 150px;min-width:150px;background:#1d2531;border:1px solid #2c3a52;border-radius:8px;padding:8px;margin:4px}
 .turnchip .oh{color:#f2c14e;font-size:12px;font-weight:700;margin-bottom:4px}
 .curves{background:#1a2029;border:1px solid #2a3342;border-radius:10px;padding:10px 14px;margin-bottom:12px}
 .curveh{color:#7c8698;font-size:11px;margin-bottom:4px}
 svg{display:block;width:100%}
 .paused{color:#f0a1a1;font-weight:700}
</style></head><body>
<h1>AoC2 AI 上帝视角控制台</h1>
<div class="sub" id="conn">连接中…</div>
<div id="alert" class="sub" style="color:#8fa3c4"></div>
<div class="cmdgrid">
  <textarea id="strategy" placeholder="输入战略指令（写入 aoc2_strategy.txt，Agent 下回合读取）"></textarea>
  <button id="btnStrategy">应用战略</button>
</div>
<div>
  <span style="color:#7c8698;font-size:12px">战略档：</span>
  <span id="gears"></span>
  <div id="gearNow" class="sub"></div>
  <button id="btnPause" class="dim" style="float:right;background:#243044;color:#b8c7dd;border:1px solid #34435c">暂停 Agent</button>
</div>
<div class="grid" id="stats"></div>
<div class="col">
  <div>
    <div class="curves"><div class="curveh">金币 / 外交点 曲线（近 40 回合）</div><svg id="svgCurve" viewBox="0 0 640 120" preserveAspectRatio="none"></svg></div>
    <div class="card">
      <div class="head"><span style="font-weight:700;color:#f2c14e">计划面板</span></div>
      <div id="plan"></div>
    </div>
    <div class="tokenbar" id="tokens">Token 统计加载中…</div>
  </div>
  <div>
    <div class="card"><div class="head"><span style="font-weight:700;color:#f2c14e">决策流</span></div><div id="cards"></div></div>
  </div>
</div>
<script>
const GEARS = /*__GEARS__*/;
let state = null, planHtml = "", rendered = new Set(), flow = [];

function req(method, path, body) {
  return fetch(path, {method, headers:{'Content-Type':'application/json'}, body: JSON.stringify(body||{})})
    .then(r => r.json()).catch(() => ({}));
}
function now() { return new Date().toLocaleTimeString(); }

async function poll() {
  let ok = true;
  try {
    const r = await fetch('/api/state');
    state = await r.json();
    document.getElementById('conn').textContent =
      '会话: ' + (state.session||'') + ' · 回合 ' + state.turn +
      ' · ' + now() + (state.paused ? ' · <b class="paused">已暂停</b>' : '');
    renderStats(); renderTokens(); renderCurve();
  } catch(e) { ok = false; document.getElementById('conn').textContent = '等待 agent 启动…'; }
  try { renderPlan(await req('GET', '/api/plan')); } catch(e) {}
  try {
    const r2 = await fetch('/api/turns');
    flow = await r2.json();
    renderFlow();
  } catch(e) {}
  return ok;
}

function el(id){ return document.getElementById(id); }

function renderStats() {
  const s = state || {};
  const st = s.state || {};
  const inc = s.income || {};
  const rows = [
    ['回合', s.turn], ['金币', st.money], ['省份', st.provinces], ['军队', st.units],
    ['行动点', st.move_points], ['外交点', st.diplomacy_points], ['科技点', st.tech_points],
    ['收入+/−', (inc.gold_in!=null? String(inc.gold_in):'?') + '/' + (inc.gold_out!=null? String(inc.gold_out):'?')],
    ['外交收入', inc.diplo_delta != null ? inc.diplo_delta : '?'],
    ['状态', (st.turn_state||'').slice(0,14)], ['消息', st.messages],
    ['邻国', (st.neighbors||[]).length], ['同化', (st.assimilates||[]).length],
    ['低稳定省', (st.low_stability_list||[]).length], ['停战', (st.truce||[]).length],
  ].filter(([k,v]) => v !== undefined);
  el('stats').innerHTML = rows.map(([k,v]) =>
    `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div></div>`).join('');
  renderGears();
  renderPauseBtn();
}

function renderTokens() {
  const s = state || {};
  const t = s.last_tokens || {prompt_tokens:0, completion_tokens:0, calls:0, cache_hit_tokens:0};
  const inM = t.prompt_tokens/1e6, outM = t.completion_tokens/1e6;
  const hitM = (t.cache_hit_tokens||0)/1e6;
  const cost = (inM * (s.cost_in||0)) + (outM * (s.cost_out||0));
  const bal = (s.balance != null) ? `　·　<b>账户余额 ¥${s.balance.toFixed(2)}</b>` : '';
  el('tokens').innerHTML =
    `累计消耗：<b>入 ${inM.toFixed(4)}M</b> / <b>出 ${outM.toFixed(4)}M</b>（缓存命中 ${hitM.toFixed(4)}M）· 调用 ${t.calls} 次` +
    `　·　估算成本 ≈ <b>¥${cost.toFixed(4)}</b>${bal}` +
    `<br>模型 ${s.model||'-'} ｜ 价 入¥${s.cost_in}/M 出¥${s.cost_out}/M`;
}

function renderGears() {
  const wrap = el('gears');
  const cur = (state && state.strategy || '');
  const idx = ['①','②','③','④','⑤','⑥'].findIndex(s => cur.startsWith(s));
  wrap.innerHTML = Array.from({length:6}, (_, i) => {
    const on = idx === i;
    const short = GEARS[i].replace(/^[①②③④⑤⑥]\s*/, '').split('：')[0].slice(0, 6);
    return `<button class="gearbtn${on?' on':''}" data-g="${i+1}" title="${GEARS[i]}">${i+1}·${short}</button>`;
  }).join('');
  el('gearNow').textContent = idx >= 0 ? ('当前战略：' + GEARS[idx]) : '当前战略：（未设档）';
  wrap.querySelectorAll('.gearbtn').forEach(b => b.onclick = async () => {
    await req('POST', '/api/command', {cmd:'gear', value: parseInt(b.dataset.g)});
    flash('战略档已写入'); setTimeout(poll, 1200);
  });
}

function renderPauseBtn() {
  const b = el('btnPause');
  const paused = !!(state && state.paused);
  b.textContent = paused ? '恢复 Agent' : '暂停 Agent';
  b.style.color = paused ? '#f0a1a1' : '#b8c7dd';
  b.onclick = async () => {
    await req('POST', '/api/command', {cmd:'pause', value: !paused});
    flash(paused ? '已恢复（删除暂停文件）' : '已暂停'); setTimeout(poll, 1200);
  };
}

function flash(msg) {
  const a = el('alert');
  a.textContent = now() + ' ' + msg;
  setTimeout(() => a.textContent = '', 4000);
}

function renderCurve() {
  const h = (state && state.history) || [];
  const pts = h.filter(p => p.money != null);
  if (pts.length < 2) { el('svgCurve').innerHTML = '<text x="10" y="14" fill="#7c8698" font-size="11">(数据不足)</text>'; return; }
  const W = 640, H = 120;
  const maxM = Math.max(...pts.map(p => p.money), 1);
  const minM = Math.min(...pts.map(p => p.money), 0);
  const moneyPath = pts.map((p, i) =>
    (i? 'L':'M') + (i * W/(pts.length-1)).toFixed(1) + ',' + (H-6-(p.money-minM)/(maxM-minM||1)*(H-14)).toFixed(1)).join(' ');
  const dips = pts.filter(p => p.diplo_pts != null);
  const maxD = Math.max(...dips.map(p => p.diplo_pts), 1);
  const dipPath = dips.map((p, i) =>
    (i? 'L':'M') + (i * W/(dips.length-1)).toFixed(1) + ',' + (H-6-p.diplo_pts/maxD*(H-14)).toFixed(1)).join(' ');
  el('svgCurve').innerHTML =
    `<line x1="0" y1="${H-6}" x2="${W}" y2="${H-6}" stroke="#2a3342"/>` +
    `<path d="${moneyPath}" fill="none" stroke="#f2c14e" stroke-width="1.6"/>` +
    `<path d="${dipPath}" fill="none" stroke="#4fc3f7" stroke-width="1.2"/>` +
    `<text x="${W-6}" y="14" fill="#f2c14e" font-size="11" text-anchor="end">金币 ${maxM}</text>` +
    `<text x="${W-6}" y="28" fill="#4fc3f7" font-size="11" text-anchor="end">外交点 ${maxD}</text>`;
}

function planCard(plan) {
  const turns = plan.turns || [];
  const brief = plan.brief ? `<div class="brief">${plan.brief}</div>` : '';
  const bodies = turns.map(t => {
    const acts = (t.actions||[]).map(a =>
      `<span class="chip">${a.action}</span>`).join('') || '<span class="chip">(无动作)</span>';
    const tac = t.tactic_ref ? `<span class="chip" style="border-color:#8a6bc0;color:#c9b3f0">tactic:${t.tactic_ref}</span>` : '';
    return `<div class="turnchip"><div class="oh">+${t.offset} 回合</div>${acts}${tac}<div style="color:#7c8698;font-size:11px;margin-top:4px">${t.note||''}</div></div>`;
  }).join('');
  const base = plan.base_provinces ? `<div class="planline">基数省: ${JSON.stringify(plan.base_provinces)}</div>` : '';
  return brief + `<div class="planbar">${bodies}</div>` + base +
    `<div class="planline">起始回合 ${plan.start_turn ?? '?'} · ${turns.length} 回合</div>`;
}

function renderPlan(p) {
  const key = JSON.stringify(p);
  if (key === planHtml || !p || !p.turns) return;   // 不变不重绘（增量）
  planHtml = key;
  el('plan').innerHTML = p.turns ? planCard(p) : '<div class="planline">（计划未生成）</div>';
}

function cardHtml(t) {
  const ph = t.mechanic_phase ? `<span class="chip" style="border-color:#2c6e6a;color:#9adfd8">阶段:${t.mechanic_phase}</span>` : '';
  const tac = t.tactic_ref ? `<span class="chip" style="border-color:#8a6bc0;color:#c9b3f0">tactic:${t.tactic_ref}</span>` : '';
  const stats = t.state ? ` · 金${t.state.money} 省${t.state.provinces} 军${t.state.units}` : '';
  const reasons = t.fail_reason ? `<span class="res fail">${t.fail_reason}</span>` : '';
  return `<div class="card">
    <div class="head"><span class="turn">回合 ${t.turn}</span>
      <span class="ts">${new Date((t.ts||0)*1000).toLocaleTimeString()}</span>${ph}${tac}
      <span class="ts">${stats}</span></div>
    <div class="brief">${t.brief||''}</div>
    <div>${(t.decision||[]).map(a=>`<span class="chip">${a.action} ${Object.entries(a).filter(([k])=>k!=='action').map(([k,v])=>k+'='+v).join(' ')}</span>`).join('')}</div>
    <div>${(t.results||[]).map(r=>`<span class="res ${(r.result||'').startsWith('OK')?'ok':'fail'}">${r.action}: ${r.result}</span>`).join('')}${reasons}</div>
    <div class="tok">${t.tokens?('Token 入'+t.tokens.prompt_tokens+' 出'+t.tokens.completion_tokens):''}</div>
  </div>`;
}

function renderFlow() {
  const wrap = el('cards');
  const uniq = {};
  flow.forEach(t => uniq[t.turn] = t);          // 同回合多点（如 skip 覆盖）
  const turns = Object.keys(uniq).map(Number).sort((a,b)=>a-b);
  turns.forEach(turn => {
    if (rendered.has(turn)) return;
    rendered.add(turn);
    wrap.insertAdjacentHTML('afterbegin', cardHtml(uniq[turn]));
    while (wrap.children.length > 80) wrap.removeChild(wrap.lastChild);
  });
}

// ---- command handlers ----
el('btnStrategy').onclick = async () => {
  const v = el('strategy').value.trim();
  if (!v) { flash('战略文本为空'); return; }
  const r = await req('POST', '/api/command', {cmd:'strategy_text', value:v});
  flash(r && r.ok ? '战略已应用' : '应用失败: ' + (r.reason||''));
};
el('btnStrategy').addEventListener('keydown', e => { if (e.key==='Enter') el('btnStrategy').click(); });
el('strategy').addEventListener('keydown', e => { if ((e.ctrlKey||e.metaKey) && e.key==='Enter') el('btnStrategy').click(); });

setInterval(poll, 2000);
poll();
</script></body></html>"""


# 注入六档文案到前端（PAGE 内 const GEARS = /*__GEARS__*/[]；JSON 转义防注入）
PAGE = PAGE.replace("/*__GEARS__*/", json.dumps(GEARS, ensure_ascii=False))


_newest_session_cache: dict = {}


def _newest_session_dir() -> None:
    """Follow the newest agent session (poll-time); dashboard survives re-games."""
    base = Path(REPO / "sessions")
    if not base.exists():
        Handler.session_dir = None
        return
    cands = [d for d in base.iterdir() if d.is_dir() and "agent" in d.name]
    if not cands:
        Handler.session_dir = None
        return
    newest = max(cands, key=lambda d: d.stat().st_mtime)
    if Handler.session_dir != newest:
        Handler.session_dir = newest


class Handler(BaseHTTPRequestHandler):
    session_dir = None
    tokens = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}
    balance = None
    cost_in = 2.0
    cost_out = 8.0
    auto_follow = True
    model = ""

    def _json(self, obj, status: int = 200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if Handler.auto_follow:
            _newest_session_dir()
        if self.path == "/":
            data = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path == "/api/state":
            self._api_state()
            return
        if self.path == "/api/turns":
            turns = load_turns(self.session_dir) if self.session_dir else []
            self._json(turns)
            return
        if self.path == "/api/plan":
            p = fetch_bridge("/plan")
            self._json(p.get("detail") or p if isinstance(p, dict) else p)
            return
        self.send_response(404)
        self.end_headers()

    def _api_state(self):
        st = fetch_state_cached()
        head = {
            "turn": st.get("turn"),
            "date": st.get("date"),
            "ledger": {
                "gold": st.get("money"),
                "move_pts": st.get("move_points"),
                "diplo_pts": st.get("diplomacy_points"),
                "tech_pts": st.get("tech_points"),
            },
            "income": st.get("income") or {},
            "state": st,
            "strategy": read_strategy_file(),
            "paused": is_paused(),
            "pause_by": pause_meta().get("pause_by"),
            "pause_ts": pause_meta().get("pause_ts"),
            "session": self.session_dir.name if self.session_dir else "",
        }
        # per-turn records → 曲线 + 最新机制阶段
        turns = load_turns(self.session_dir) if self.session_dir else []
        if turns:
            last = turns[-1]
            head["mechanic_phase"] = last.get("mechanic_phase")
            head["tactic_ref"] = last.get("tactic_ref")
            head["history"] = history_for_curve(turns)
            tok = last.get("tokens_cum")
            if tok:
                self.tokens = dict(tok)
            if last.get("balance") is not None:
                self.balance = last["balance"]
        head["last_tokens"] = dict(self.tokens)
        head["balance"] = self.balance
        head["cost_in"] = self.cost_in
        head["cost_out"] = self.cost_out
        head["model"] = self.model
        self._json(head)

    def do_POST(self):
        if self.path == "/api/command":
            self._api_command()
            return
        self.send_response(404)
        self.end_headers()

    def _api_command(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as e:
            self._json({"ok": False, "reason": f"bad json: {e}"}, 400)
            return
        cmd = data.get("cmd")
        value = data.get("value")
        if cmd == "gear":
            ok = apply_gear(value)
        elif cmd == "strategy_text":
            ok = apply_strategy_text(value)
        elif cmd == "pause":
            ok = apply_pause(value)
        else:
            self._json({"ok": False, "reason": f"unknown cmd: {cmd}"}, 400)
            return
        self._json({"ok": ok, "cmd": cmd})

    def log_message(self, *args):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--session", default=None)
    args = ap.parse_args()
    try:
        import yaml
        cfg_path = REPO / "config.yaml"
        if cfg_path.exists():
            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            llm_cfg = cfg.get("llm", {})
            Handler.cost_in = float(llm_cfg.get("cost_per_1m_input", Handler.cost_in))
            Handler.cost_out = float(llm_cfg.get("cost_per_1m_output", Handler.cost_out))
            Handler.model = llm_cfg.get("openai_compat", {}).get("model", Handler.model)
    except Exception:
        pass
    if args.session:
        Handler.session_dir = Path(args.session)
        Handler.auto_follow = False
    else:
        _newest_session_dir()
    if Handler.session_dir:
        for t in load_turns(Handler.session_dir):
            if t.get("tokens_cum"):
                Handler.tokens = dict(t["tokens_cum"])
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"dashboard: http://127.0.0.1:{args.port}  (session {Handler.session_dir})")
    server.serve_forever()


if __name__ == "__main__":
    main()
