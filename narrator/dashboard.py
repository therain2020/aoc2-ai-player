"""God-view dashboard: local HTTP server showing live game state, agent turns,
decisions, narration and LLM token usage.

Usage: python -m narrator.dashboard [--port 8080] [--session <dir>]
Then open http://127.0.0.1:8080 in a browser.
"""
import argparse
import json
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BRIDGE = "http://127.0.0.1:9110"

PAGE = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>AoC2 AI 上帝视角控制台</title>
<style>
 body{font-family:"Microsoft YaHei",sans-serif;background:#0f1218;color:#dde2ea;margin:0;padding:20px;max-width:980px;margin:0 auto}
 h1{font-size:18px;color:#f2c14e;margin:0 0 4px}
 .sub{color:#7c8698;font-size:12px;margin-bottom:14px}
 .grid{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}
 .stat{background:#1a2029;border:1px solid #2a3342;border-radius:10px;padding:10px 14px;min-width:110px}
 .stat .k{color:#7c8698;font-size:11px}
 .stat .v{color:#e8ecf2;font-size:20px;font-weight:700;margin-top:2px}
 .stat .v.small{font-size:14px}
 .tokenbar{background:#1a2029;border:1px solid #2a3342;border-radius:10px;padding:10px 14px;margin-bottom:16px;font-size:13px}
 .tokenbar b{color:#f2c14e}
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
</style></head><body>
<h1>AoC2 AI 上帝视角控制台</h1>
<div class="sub" id="conn">连接中…</div>
<div class="grid" id="stats"></div>
<div class="tokenbar" id="tokens">Token 统计加载中…</div>
<div id="cards"></div>
<script>
let state = null, turns = [];
async function poll() {
  try {
    const r = await fetch('/api/state');
    state = await r.json();
    document.getElementById('conn').textContent = '会话: ' + (state.session||'') + ' · ' + new Date().toLocaleTimeString();
    renderStats();
    renderTokens();
  } catch(e) { document.getElementById('conn').textContent = '等待 agent 启动…'; }
  try {
    const r2 = await fetch('/api/turns');
    turns = await r2.json();
    renderCards();
  } catch(e) {}
}
function renderStats() {
  const s = state;
  const el = document.getElementById('stats');
  el.innerHTML = [
    ['回合', s.turn], ['金币', s.money], ['省份', s.provinces], ['军队', s.units],
    ['科技点', s.tech_points], ['状态', (s.turn_state||'').slice(0,14)],
    ['消息', s.messages], ['邻国', (s.neighbors||[]).length],
  ].map(([k,v]) => `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div></div>`).join('');
}
function renderTokens() {
  const t = state.tokens || {prompt_tokens:0, completion_tokens:0, calls:0, cache_hit_tokens:0};
  const inM = t.prompt_tokens/1e6, outM = t.completion_tokens/1e6;
  const hitM = (t.cache_hit_tokens||0)/1e6;
  const cost = (inM * (state.cost_in||0)) + (outM * (state.cost_out||0));
  const bal = (state.balance != null) ? `　·　<b>账户余额 ¥${state.balance.toFixed(2)}</b>` : '';
  document.getElementById('tokens').innerHTML =
    `累计消耗：<b>入 ${inM.toFixed(4)}M</b> / <b>出 ${outM.toFixed(4)}M</b>（缓存命中 ${hitM.toFixed(4)}M）· 调用 ${t.calls} 次` +
    `　·　估算成本 ≈ <b>¥${cost.toFixed(4)}</b>${bal}` +
    `<br>模型 ${state.model||'-'} ｜ 价 入¥${state.cost_in}/M 出¥${state.cost_out}/M`;
}
function renderCards() {
  const el = document.getElementById('cards');
  el.innerHTML = turns.slice(-60).reverse().map(t => `
    <div class="card">
      <div class="head"><span class="turn">回合 ${t.turn}</span><span class="ts">${new Date((t.ts||0)*1000).toLocaleTimeString()}</span></div>
      <div class="brief">${t.brief||''}</div>
      <div>${(t.decision||[]).map(a=>`<span class="chip">${a.action} ${Object.entries(a).filter(([k])=>k!=='action').map(([k,v])=>k+'='+v).join(' ')}</span>`).join('')}</div>
      <div>${(t.results||[]).map(r=>`<span class="res ${(r.result||'').startsWith('OK')?'ok':'fail'}">${r.action}: ${r.result}</span>`).join('')}</div>
      <div class="tok">${t.tokens?('Token 入'+t.tokens.prompt_tokens+' 出'+t.tokens.completion_tokens):''}</div>
    </div>`).join('');
}
setInterval(poll, 2000);
poll();
</script></body></html>"""


def fetch_bridge(path: str) -> dict:
    try:
        with urllib.request.urlopen(BRIDGE + path, timeout=4) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return {}


class Handler(BaseHTTPRequestHandler):
    session_dir = None
    tokens = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}
    balance = None
    cost_in = 2.0
    cost_out = 8.0
    model = "deepseek-chat"

    def _json(self, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            data = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path == "/api/state":
            st = fetch_bridge("/state")
            st["session"] = self.session_dir.name if self.session_dir else ""
            # live token totals: re-read newest turns.jsonl every poll
            if self.session_dir:
                path = self.session_dir / "turns.jsonl"
                if path.exists():
                    try:
                        with open(path, "rb") as f:
                            f.seek(0, 2)
                            pos = max(0, f.tell() - 16384)
                            f.seek(pos)
                            for line in f.read().decode("utf-8", "replace").splitlines():
                                try:
                                    t = json.loads(line)
                                    if t.get("tokens_cum"):
                                        self.tokens = dict(t["tokens_cum"])
                                    if t.get("balance") is not None:
                                        self.balance = t["balance"]
                                except json.JSONDecodeError:
                                    continue
                    except OSError:
                        pass
            st["tokens"] = dict(self.tokens)
            st["balance"] = self.balance
            st["cost_in"] = self.cost_in
            st["cost_out"] = self.cost_out
            st["model"] = self.model
            self._json(st)
            return
        if self.path == "/api/turns":
            turns = []
            if self.session_dir:
                path = self.session_dir / "turns.jsonl"
                if path.exists():
                    with open(path, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                turns.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
            self._json(turns)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, *args):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--session", default=None)
    args = ap.parse_args()
    # pricing + model from config.yaml (fall back to defaults)
    try:
        import yaml
        cfg_path = Path(REPO / "config.yaml")
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
    else:
        base = Path(REPO / "sessions")
        dirs = [d for d in base.iterdir() if d.is_dir() and "agent" in d.name]
        if dirs:
            Handler.session_dir = max(dirs, key=lambda d: d.stat().st_mtime)
    # pull accumulated tokens from newest turns
    if Handler.session_dir:
        path = Handler.session_dir / "turns.jsonl"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        t = json.loads(line)
                        if t.get("tokens_cum"):
                            Handler.tokens = dict(t["tokens_cum"])
                    except json.JSONDecodeError:
                        continue
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"dashboard: http://127.0.0.1:{args.port}  (session {Handler.session_dir})")
    server.serve_forever()


if __name__ == "__main__":
    main()
