"""Flask web server — browse and read generated briefs in the browser.

Railway will run this as the web service. Brief files are read from
OUTPUT_DIR (defaults to ./output, override with the OUTPUT_DIR env var
or by mounting a Railway volume at /data and setting OUTPUT_DIR=/data/output).
"""

import os
import re
from pathlib import Path
from datetime import datetime
from flask import Flask, abort, render_template_string

app = Flask(__name__)
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", Path(__file__).parent / "output"))

# ── Brief → HTML conversion ────────────────────────────────────────────────

def _text_to_html(text: str) -> str:
    """Convert plain-text brief to lightweight HTML."""
    lines = text.splitlines()
    html_lines = []
    for line in lines:
        esc = (line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

        if re.match(r"^[═─━]{5,}", esc):
            html_lines.append('<hr class="rule">')
        elif esc.startswith("  ") and re.match(r"^\s+\w", esc):
            html_lines.append(f'<p class="indent">{esc.strip()}</p>')
        elif re.match(r"^[IVX]+\.\s", esc):
            html_lines.append(f'<h2 class="section-h">{esc}</h2>')
        elif re.match(r"^¶\d+", esc):
            num, _, rest = esc.partition(" ")
            html_lines.append(
                f'<div class="fact-row"><span class="para-n">{num}</span>'
                f'<span class="para-body">{rest}</span></div>'
            )
        elif re.match(r"^AT A GLANCE|^COMMONWEALTH v\.|^Daily Case Brief|^Docket No\.", esc):
            html_lines.append(f'<p class="caption-line">{esc}</p>')
        elif re.match(r"^\s*▸", esc):
            html_lines.append(f'<li class="glance-item">{esc.lstrip("▸ ").strip()}</li>')
        elif re.match(r"^\s*─+\s*$", esc):
            html_lines.append('<hr class="minor-rule">')
        elif esc.strip() == "":
            html_lines.append('<div class="spacer"></div>')
        else:
            flagged = re.sub(
                r"\[(UNCONFIRMED|UNVERIFIED|SLEUTH THEORY|FALSE|TRUE|PARTIAL|DISPUTED|JURY POOL RISK)\]",
                r'<span class="flag flag-\1">\1</span>',
                esc,
            )
            html_lines.append(f'<p>{flagged}</p>')

    return "\n".join(html_lines)


# ── Templates ───────────────────────────────────────────────────────────────

INDEX_TMPL = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Clancy Case Monitor</title>
<style>
:root{--bg:#F5F4EF;--surface:#EDEBE4;--border:#C8C5BC;--text:#1A1917;--muted:#6B6860;--red:#9B2626;--blue:#1C3A72}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0E0D0B;--surface:#171614;--border:#2A2926;--text:#E8E5DC;--muted:#8A877E;--red:#C94040;--blue:#6B8FD4}}
:root[data-theme=dark]{--bg:#0E0D0B;--surface:#171614;--border:#2A2926;--text:#E8E5DC;--muted:#8A877E;--red:#C94040;--blue:#6B8FD4}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:Georgia,serif;padding:2rem 1rem 4rem}
.wrap{max-width:680px;margin:0 auto}
.cap-rule{height:4px;background:var(--red);margin-bottom:2rem}
h1{font-size:1.3rem;margin-bottom:.3rem}
.subtitle{font-family:"Courier New",monospace;font-size:.75rem;color:var(--muted);margin-bottom:2rem}
.brief-list{list-style:none;display:flex;flex-direction:column;gap:.6rem}
.brief-item a{display:flex;justify-content:space-between;align-items:center;padding:.9rem 1.1rem;background:var(--surface);border:1px solid var(--border);color:var(--text);text-decoration:none;font-family:"Courier New",monospace;font-size:.85rem}
.brief-item a:hover{border-color:var(--red)}
.brief-date{font-weight:bold}
.brief-label{color:var(--muted);font-size:.72rem}
.empty{color:var(--muted);font-family:"Courier New",monospace;font-size:.85rem;padding:1.5rem 0}
</style>
</head>
<body>
<div class="wrap">
  <div class="cap-rule"></div>
  <h1>Commonwealth v. Lindsay Clancy</h1>
  <p class="subtitle">CLANCY CASE MONITOR — DAILY BRIEFS</p>
  {% if briefs %}
  <ul class="brief-list">
    {% for b in briefs %}
    <li class="brief-item">
      <a href="/brief/{{ b.date }}">
        <span class="brief-date">{{ b.label }}</span>
        <span class="brief-label">VIEW BRIEF →</span>
      </a>
    </li>
    {% endfor %}
  </ul>
  {% else %}
  <p class="empty">No briefs generated yet. Run <code>python agent.py</code> to generate the first one.</p>
  {% endif %}
</div>
</body>
</html>
"""

BRIEF_TMPL = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Clancy Brief {{ date }}</title>
<style>
:root{--bg:#F5F4EF;--surface:#EDEBE4;--border:#C8C5BC;--text:#1A1917;--muted:#6B6860;--red:#9B2626;--blue:#1C3A72;--green-bg:#E6F0E8;--green-txt:#1D5C35;--amber-bg:#F5EDD8;--amber-txt:#6B4A00;--red-bg:#F5E4E4;--red-txt:#7A1E1E;--purple-bg:#EDE8F5;--purple-txt:#3D2A6B}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0E0D0B;--surface:#171614;--border:#2A2926;--text:#E8E5DC;--muted:#8A877E;--red:#C94040;--blue:#6B8FD4;--green-bg:#0F2218;--green-txt:#5EC47E;--amber-bg:#1E1600;--amber-txt:#D4A83A;--red-bg:#200A0A;--red-txt:#D46060;--purple-bg:#140E22;--purple-txt:#B09AE0}}
:root[data-theme=dark]{--bg:#0E0D0B;--surface:#171614;--border:#2A2926;--text:#E8E5DC;--muted:#8A877E;--red:#C94040;--blue:#6B8FD4;--green-bg:#0F2218;--green-txt:#5EC47E;--amber-bg:#1E1600;--amber-txt:#D4A83A;--red-bg:#200A0A;--red-txt:#D46060;--purple-bg:#140E22;--purple-txt:#B09AE0}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:Georgia,serif;font-size:15px;line-height:1.75;padding:2rem 1rem 4rem}
.wrap{max-width:760px;margin:0 auto}
.cap-rule{height:4px;background:var(--red);margin-bottom:2rem}
.back{font-family:"Courier New",monospace;font-size:.75rem;color:var(--muted);text-decoration:none;display:inline-block;margin-bottom:1.5rem}
.back:hover{color:var(--red)}
hr.rule{border:none;border-top:1.5px solid var(--border);margin:1.8rem 0}
hr.minor-rule{border:none;border-top:1px solid var(--border);margin:1rem 0}
.section-h{font-family:"Courier New",monospace;font-size:.78rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin:2rem 0 .9rem}
.caption-line{font-family:"Courier New",monospace;font-size:.82rem;color:var(--muted);text-align:center;line-height:1.8}
.fact-row{display:grid;grid-template-columns:2.4rem 1fr;gap:0 .6rem;margin:.75rem 0}
.para-n{font-family:"Courier New",monospace;font-size:.82rem;color:var(--red);text-align:right;padding-top:.1em}
.glance-item{margin-left:1.5rem;margin-bottom:.4rem}
.spacer{height:.5rem}
.indent{padding-left:1.5rem}
.flag{display:inline-block;font-family:"Courier New",monospace;font-size:.68rem;font-weight:bold;padding:.1em .45em;border-radius:2px;vertical-align:middle;margin:0 .2rem;text-transform:uppercase}
.flag-UNCONFIRMED,.flag-UNVERIFIED{background:var(--amber-bg);color:var(--amber-txt)}
.flag-SLEUTH\.THEORY,.flag-SLEUTH.THEORY{background:var(--purple-bg);color:var(--purple-txt)}
.flag-FALSE,.flag-DISPUTED{background:var(--red-bg);color:var(--red-txt)}
.flag-TRUE{background:var(--green-bg);color:var(--green-txt)}
.flag-PARTIAL{background:var(--amber-bg);color:var(--amber-txt)}
p{margin:.5rem 0}
</style>
</head>
<body>
<div class="wrap">
  <div class="cap-rule"></div>
  <a class="back" href="/">← All Briefs</a>
  <div>{{ content|safe }}</div>
</div>
</body>
</html>
"""


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
    return render_template_string(INDEX_TMPL, briefs=briefs)


@app.route("/brief/latest")
def latest():
    briefs = sorted(OUTPUT_DIR.glob("brief_*.txt"), reverse=True)
    if not briefs:
        abort(404)
    date_str = briefs[0].stem.replace("brief_", "")
    from flask import redirect
    return redirect(f"/brief/{date_str}")


@app.route("/brief/<date_str>")
def view_brief(date_str: str):
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        abort(400)
    path = OUTPUT_DIR / f"brief_{date_str}.txt"
    if not path.exists():
        abort(404)
    raw = path.read_text(encoding="utf-8")
    html_content = _text_to_html(raw)
    return render_template_string(BRIEF_TMPL, date=date_str, content=html_content)


@app.route("/health")
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
