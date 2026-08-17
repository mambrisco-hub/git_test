"""Flask web server — browse briefs and trigger generation on demand.

Railway runs this as the web service. Briefs are stored in OUTPUT_DIR
(default ./output; set OUTPUT_DIR=/data/output when using a Railway Volume).

Routes:
  GET  /                — list all briefs, with a Generate button
  GET  /brief/latest    — redirect to most recent brief
  GET  /brief/<date>    — view a specific brief
  POST /generate        — kick off agent.py in a background thread
  GET  /status          — JSON status of any running generation
  GET  /health          — Railway health check
"""

import os
import re
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template_string, request, url_for
from markupsafe import Markup

app = Flask(__name__)
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", Path(__file__).parent / "output"))

# ── Generation state ────────────────────────────────────────────────────────

_gen_lock = threading.Lock()
_gen_state = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "error": None,
    "last_date": None,
}


def _run_agent():
    with _gen_lock:
        _gen_state["running"] = True
        _gen_state["started_at"] = datetime.now(timezone.utc).isoformat()
        _gen_state["error"] = None

    try:
        result = subprocess.run(
            ["python", str(Path(__file__).parent / "agent.py")],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(Path(__file__).parent),
        )
        if result.returncode != 0:
            _gen_state["error"] = (result.stderr or result.stdout)[-1000:]
        else:
            _gen_state["last_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    except subprocess.TimeoutExpired:
        _gen_state["error"] = "Agent timed out after 10 minutes."
    except Exception as exc:
        _gen_state["error"] = str(exc)
    finally:
        _gen_state["running"] = False
        _gen_state["finished_at"] = datetime.now(timezone.utc).isoformat()


# ── Brief → HTML ────────────────────────────────────────────────────────────

def _brief_to_html(text: str) -> str:
    lines = text.splitlines()
    out = []
    for line in lines:
        e = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        def flag(m):
            word = m.group(1).replace(" ", "-")
            return f'<span class="flag flag-{word}">{m.group(1)}</span>'

        e = re.sub(
            r"\[(UNCONFIRMED|UNVERIFIED|SLEUTH THEORY|FALSE|TRUE|PARTIAL|DISPUTED|JURY POOL RISK)\]",
            flag, e,
        )

        if re.match(r"^[═─━]{5,}", e):
            out.append('<hr class="rule">')
        elif re.match(r"^[IVX]+\.\s", e.strip()):
            out.append(f'<h2 class="sh">{e.strip()}</h2>')
        elif re.match(r"^¶\d+", e.strip()):
            num, _, rest = e.strip().partition(" ")
            out.append(f'<div class="fp"><span class="pn">{num}</span><span>{rest}</span></div>')
        elif re.match(r"^\s*▸", e):
            out.append(f'<li class="gi">{e.lstrip("▸ ").strip()}</li>')
        elif e.strip() == "":
            out.append('<div class="sp"></div>')
        else:
            out.append(f'<p>{e}</p>')
    return "\n".join(out)


# ── Shared CSS ──────────────────────────────────────────────────────────────

CSS = Markup("""
<style>
:root{--bg:#F5F4EF;--sf:#EDEBE4;--br:#C8C5BC;--tx:#1A1917;--mu:#6B6860;--rd:#9B2626;--bl:#1C3A72;--gb:#E6F0E8;--gt:#1D5C35;--ab:#F5EDD8;--at:#6B4A00;--rb:#F5E4E4;--rt:#7A1E1E;--pb:#EDE8F5;--pt:#3D2A6B}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0E0D0B;--sf:#171614;--br:#2A2926;--tx:#E8E5DC;--mu:#8A877E;--rd:#C94040;--bl:#6B8FD4;--gb:#0F2218;--gt:#5EC47E;--ab:#1E1600;--at:#D4A83A;--rb:#200A0A;--rt:#D46060;--pb:#140E22;--pt:#B09AE0}}
:root[data-theme=dark]{--bg:#0E0D0B;--sf:#171614;--br:#2A2926;--tx:#E8E5DC;--mu:#8A877E;--rd:#C94040;--bl:#6B8FD4;--gb:#0F2218;--gt:#5EC47E;--ab:#1E1600;--at:#D4A83A;--rb:#200A0A;--rt:#D46060;--pb:#140E22;--pt:#B09AE0}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--tx);font-family:Georgia,serif;font-size:15px;line-height:1.75;padding:2rem 1rem 4rem}
.wrap{max-width:760px;margin:0 auto}
.cap-rule{height:4px;background:var(--rd);margin-bottom:2rem}
a{color:var(--bl)}
.flag{display:inline-block;font-family:"Courier New",monospace;font-size:.68rem;font-weight:bold;padding:.1em .45em;border-radius:2px;vertical-align:middle;margin:0 .2rem;text-transform:uppercase}
.flag-UNCONFIRMED,.flag-UNVERIFIED{background:var(--ab);color:var(--at)}
.flag-SLEUTH-THEORY{background:var(--pb);color:var(--pt)}
.flag-FALSE,.flag-DISPUTED,.flag-JURY-POOL-RISK{background:var(--rb);color:var(--rt)}
.flag-TRUE{background:var(--gb);color:var(--gt)}
.flag-PARTIAL{background:var(--ab);color:var(--at)}
.sh{font-family:"Courier New",monospace;font-size:.78rem;letter-spacing:.14em;text-transform:uppercase;color:var(--mu);margin:2rem 0 .9rem}
.fp{display:grid;grid-template-columns:2.4rem 1fr;gap:0 .6rem;margin:.75rem 0}
.pn{font-family:"Courier New",monospace;font-size:.82rem;color:var(--rd);text-align:right;padding-top:.1em}
.gi{margin-left:1.5rem;margin-bottom:.4rem}
.sp{height:.5rem}
hr.rule{border:none;border-top:1.5px solid var(--br);margin:1.8rem 0}
p{margin:.5rem 0}
</style>
""")


# ── Templates ───────────────────────────────────────────────────────────────

INDEX_TMPL = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Clancy Case Monitor</title>
{{ css }}
<style>
h1{font-size:1.35rem;margin-bottom:.25rem}
.sub{font-family:"Courier New",monospace;font-size:.75rem;color:var(--mu);margin-bottom:2rem}
.toolbar{display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem;flex-wrap:wrap}
.btn{font-family:"Courier New",monospace;font-size:.78rem;letter-spacing:.08em;text-transform:uppercase;padding:.55rem 1.1rem;border:none;cursor:pointer;text-decoration:none;display:inline-block}
.btn-primary{background:var(--rd);color:#fff}
.btn-primary:hover{opacity:.88}
.btn-primary:disabled{opacity:.45;cursor:not-allowed}
.status-msg{font-family:"Courier New",monospace;font-size:.72rem;color:var(--mu)}
.status-ok{color:var(--gt)}
.status-err{color:var(--rt)}
.brief-list{list-style:none;display:flex;flex-direction:column;gap:.55rem}
.brief-item a{display:flex;justify-content:space-between;align-items:center;padding:.85rem 1.1rem;background:var(--sf);border:1px solid var(--br);color:var(--tx);text-decoration:none;font-family:"Courier New",monospace;font-size:.85rem}
.brief-item a:hover{border-color:var(--rd)}
.brief-date{font-weight:bold}
.brief-arr{color:var(--mu);font-size:.72rem}
.empty{color:var(--mu);font-family:"Courier New",monospace;font-size:.85rem;padding:1rem 0}
#gen-status{display:none}
</style>
<script>
function submitGenerate(e){
  const btn=document.getElementById('gen-btn');
  const msg=document.getElementById('gen-status');
  btn.disabled=true;
  btn.textContent='Generating…';
  msg.style.display='inline';
  msg.textContent='Running — this takes about 60 seconds. Refresh the page in a minute.';
  msg.className='status-msg';
}
function checkStatus(){
  fetch('/status').then(r=>r.json()).then(d=>{
    const btn=document.getElementById('gen-btn');
    const msg=document.getElementById('gen-status');
    if(d.running){
      btn.disabled=true;btn.textContent='Generating…';
      msg.style.display='inline';msg.textContent='Running… refresh in a moment.';
      msg.className='status-msg';
      setTimeout(checkStatus,5000);
    } else {
      btn.disabled=false;btn.textContent='Generate Now';
      if(d.error){msg.style.display='inline';msg.textContent='Error: '+d.error.slice(0,120);msg.className='status-msg status-err';}
      else if(d.finished_at){msg.style.display='inline';msg.textContent='Done — reload to see the new brief.';msg.className='status-msg status-ok';}
    }
  }).catch(()=>setTimeout(checkStatus,8000));
}
document.addEventListener('DOMContentLoaded',()=>{checkStatus();});
</script>
</head><body>
<div class="wrap">
  <div class="cap-rule"></div>
  <h1>Commonwealth v. Lindsay Clancy</h1>
  <p class="sub">CLANCY CASE MONITOR — DAILY BRIEFS</p>

  <div class="toolbar">
    <form method="POST" action="/generate" onsubmit="submitGenerate(event)">
      <button class="btn btn-primary" id="gen-btn" type="submit">Generate Now</button>
    </form>
    <span id="gen-status" class="status-msg"></span>
  </div>

  {% if briefs %}
  <ul class="brief-list">
    {% for b in briefs %}
    <li class="brief-item">
      <a href="/brief/{{ b.date }}">
        <span class="brief-date">{{ b.label }}</span>
        <span class="brief-arr">VIEW →</span>
      </a>
    </li>
    {% endfor %}
  </ul>
  {% else %}
  <p class="empty">No briefs yet — hit Generate Now to create the first one.</p>
  {% endif %}
</div></body></html>"""

BRIEF_TMPL = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Clancy Brief {{ date }}</title>
{{ css }}
<style>
.topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem;flex-wrap:wrap;gap:.6rem}
.back{font-family:"Courier New",monospace;font-size:.75rem;color:var(--mu);text-decoration:none}
.back:hover{color:var(--rd)}
.btn-sm{font-family:"Courier New",monospace;font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;padding:.4rem .9rem;background:var(--rd);color:#fff;border:none;cursor:pointer;text-decoration:none}
</style>
</head><body>
<div class="wrap">
  <div class="cap-rule"></div>
  <div class="topbar">
    <a class="back" href="/">← All Briefs</a>
    <a class="btn-sm" href="/">↺ Generate New</a>
  </div>
  {{ content|safe }}
</div></body></html>"""


# ── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    brief_files = sorted(OUTPUT_DIR.glob("brief_*.txt"), reverse=True)
    briefs = []
    for f in brief_files:
        date_str = f.stem.replace("brief_", "")
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            label = dt.strftime("%A, %B %-d, %Y")
        except ValueError:
            label = date_str
        briefs.append({"date": date_str, "label": label})
    return render_template_string(INDEX_TMPL, briefs=briefs, css=CSS)


@app.route("/generate", methods=["POST"])
def generate():
    if not _gen_state["running"]:
        t = threading.Thread(target=_run_agent, daemon=True)
        t.start()
    return redirect(url_for("index"))


@app.route("/status")
def status():
    return jsonify({
        "running": _gen_state["running"],
        "started_at": _gen_state["started_at"],
        "finished_at": _gen_state["finished_at"],
        "error": _gen_state["error"],
        "last_date": _gen_state["last_date"],
    })


@app.route("/brief/latest")
def latest():
    briefs = sorted(OUTPUT_DIR.glob("brief_*.txt"), reverse=True)
    if not briefs:
        abort(404)
    date_str = briefs[0].stem.replace("brief_", "")
    return redirect(f"/brief/{date_str}")


@app.route("/brief/<date_str>")
def view_brief(date_str: str):
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        abort(400)
    path = OUTPUT_DIR / f"brief_{date_str}.txt"
    if not path.exists():
        abort(404)
    raw = path.read_text(encoding="utf-8")
    return render_template_string(BRIEF_TMPL, date=date_str, content=_brief_to_html(raw), css=CSS)


@app.route("/health")
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
