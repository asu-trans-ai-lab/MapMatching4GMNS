"""Visual review export — a self-contained dashboard + review-record scaffold.

Aligned with GUI4GMNS's offline, self-contained philosophy: one `dashboard.html` (no external
JS), layer files, and a `match_review.csv` for a reproducible human-in-the-loop correction
history. This is the visual-review responsibility; it does NOT edit the GMNS network.
"""
import csv
import json
import os

_DECISIONS = ["ACCEPT_TRUSTED", "ACCEPT_HMM", "ACCEPT_GEOMETRIC", "REPLACE_PATH", "INSUFFICIENT_EVIDENCE"]


def _link_coords(link_geom, links):
    out = []
    for l in links or []:
        pts = link_geom.get(str(l))
        if pts:
            out.append(pts)
    return out


def export(out_dir, trace_df, routes, case_id, verdict, link_geom=None):
    link_geom = link_geom or {}
    layers = os.path.join(out_dir, "dashboard_layers"); os.makedirs(layers, exist_ok=True)
    tpts = [[float(x), float(y)] for x, y in zip(trace_df["x_coord"], trace_df["y_coord"])]
    data = {"raw_trace": tpts,
            "hmm_route": _link_coords(link_geom, routes.get("hmm")),
            "geometric_route": _link_coords(link_geom, routes.get("geometric")),
            "trusted_route": _link_coords(link_geom, routes.get("trusted"))}
    for name, d in data.items():
        json.dump(d, open(os.path.join(layers, name + ".js"), "w"))

    # match_review.csv scaffold (review contract)
    with open(os.path.join(out_dir, "match_review.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["review_id", "trace_id", "issue_type", "hmm_link_ids", "geometric_link_ids",
                    "trusted_link_ids", "review_status", "reviewer_decision", "replacement_link_ids", "review_note"])
        w.writerow([1, case_id, "", ";".join(routes.get("hmm") or []),
                    ";".join(routes.get("geometric") or []), ";".join(routes.get("trusted") or []),
                    "OPEN", "", "", f"allowed decisions: {'|'.join(_DECISIONS)}"])

    # self-contained dashboard (inline SVG, layer toggles)
    allpts = tpts + [p for seg in data["trusted_route"] + data["geometric_route"] for p in seg]
    xs = [p[0] for p in allpts] or [0]; ys = [p[1] for p in allpts] or [0]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    W, H, pad = 900, 460, 40
    sx = lambda x: pad + (x - minx) / max(1e-9, maxx - minx) * (W - 2 * pad)
    sy = lambda y: H - pad - (y - miny) / max(1e-9, maxy - miny) * (H - 2 * pad)

    def poly(segs, cls):
        return "".join(f'<polyline class="{cls}" points="{" ".join(f"{sx(x):.1f},{sy(y):.1f}" for x,y in seg)}"/>' for seg in segs)
    trace_dots = "".join(f'<circle class="trace" cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="3"/>' for x, y in tpts)
    color = {"PASS": "#2f855a", "PASS_WITH_ENGINE_DISAGREEMENT": "#b7791f",
             "REVIEW_REQUIRED": "#c05621", "FAIL": "#c53030"}.get(verdict, "#4a5568")
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>MapMatching4GMNS — {case_id}</title>
<style>body{{font:14px system-ui;margin:16px;color:#1a202c}}
svg{{border:1px solid #e2e8f0;background:#fff}} .trace{{fill:#3182ce;opacity:.7}}
.geometric{{stroke:#dd6b20;stroke-width:2.5;fill:none;opacity:.8}} .trusted{{stroke:#2b6cb0;stroke-width:3.5;fill:none}}
.hmm{{stroke:#38a169;stroke-width:2;fill:none;stroke-dasharray:5 3;opacity:.85}}
label{{margin-right:14px}} .badge{{padding:3px 10px;border-radius:6px;color:#fff;background:{color}}}</style></head>
<body><h2>MapMatching4GMNS self-demo — {case_id} <span class="badge">{verdict}</span></h2>
<div><label><input type=checkbox checked onclick="t('traceL',this)">raw trace</label>
<label><input type=checkbox checked onclick="t('hmmL',this)">HMM route</label>
<label><input type=checkbox checked onclick="t('geoL',this)">geometric route</label>
<label><input type=checkbox checked onclick="t('trustL',this)">trusted route</label></div>
<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<g id="geoL">{poly(data['geometric_route'],'geometric')}</g>
<g id="hmmL">{poly(data['hmm_route'],'hmm')}</g>
<g id="trustL">{poly(data['trusted_route'],'trusted')}</g>
<g id="traceL">{trace_dots}</g></svg>
<p>trusted links: {len(routes.get('trusted') or [])} · geometric: {len(routes.get('geometric') or [])} · hmm: {len(routes.get('hmm') or []) if routes.get('hmm') is not None else 'skipped'} — review record in match_review.csv</p>
<script>function t(id,c){{document.getElementById(id).style.display=c.checked?'':'none'}}</script></body></html>"""
    open(os.path.join(out_dir, "dashboard.html"), "w", encoding="utf-8").write(html)
    return os.path.join(out_dir, "dashboard.html")
