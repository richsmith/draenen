"""The site: a landing page, the 3D view and route planner, and the data.

    python3 -m tools.site          # writes site/ (CHROMIUM set: with a preview image)
    python3 -m http.server -d site # then open http://localhost:8000

site/index.html  the landing page: what it is, ready-made routes, using it
                 underground, the data and the credits
site/3d/         the 3D view and route planner (tools/model3d)
site/data/       the survey as Therion builds it: the plan (PDF) and the .3d

Build the survey first (cd survey && therion draenen.thconfig). GitHub
Actions builds both and publishes the site to GitHub Pages
(.github/workflows/build.yml). Plain Python, no packages.
"""
import datetime
import heapq
import html
import json
import math
import os
import shutil
import sys

from tools.model3d.__main__ import build as build_3d

OUT = 'site'
REPO = 'https://github.com/richsmith/draenen'
OUCC = 'https://www.oucc.org.uk/surveys/surveys%20and%20data%20-%20draenen/survex/draenen_survex_data.htm'
DATA = [
    ('draenen-plan.pdf', 'The plan', 'The survey at 1:5000, drawn in Therion and coloured by altitude: the centreline, the drawn passages, the passage names and the entrances, with the length, depth and credits.'),
    ('draenen.3d', 'The survey, processed by Therion', 'Survex 3D file of the whole cave. Open it in Aven. The 3D view and the routes are made from it. Fixed on the National Grid at the entrance, heights above sea level.'),
]
# ready-made routes on the landing page: these from the entrance, and from
# each other entrance, every place nearer from there than from the entrance
# (and more than NEAR metres in)
NEAR = 200
# said under an entrance's routes
NOTES = {
    'Tarddiad Pwll Du': "The shorter way into the north of the cave. Tarddiad Pwll Du's tie into the survey is "
                        "provisional (it's tied in at the base of the Waterfall Series' first climb until the real "
                        "tie is known), so for now these routes start there, without the way through Tarddiad itself.",
}
ROUTES = ['Big Country', 'Life on Mars', 'Waterfall Series', 'Gilwern Passage', 'Megadrive', 'The Score',
          'Luck of the Draw', 'Out of the Blue', 'Blood River', 'Crystal Maze', 'Indiana Highway', 'Gone in the Years']


def routes(scene):
    """The ready-made routes: {from: [(to, length, up, down, passages)]},
    the entrance first."""
    g = scene['graph']
    pos = [g['pos'][i:i + 3] for i in range(0, len(g['pos']), 3)]
    adj = [[] for _ in pos]
    for k in range(0, len(g['edges']), 2):
        a, b = g['edges'][k], g['edges'][k + 1]
        d = math.dist(pos[a], pos[b])
        adj[a].append((b, d))
        adj[b].append((a, d))
    node = {n['t']: min(range(len(pos)), key=lambda i: math.dist(pos[i], n['p'])) for n in scene['names']}

    def path(a, b):
        dist, prev, q = {a: 0}, {}, [(0, a)]
        while q:
            d, u = heapq.heappop(q)
            if u == b:
                break
            if d > dist[u]:
                continue
            for v, c in adj[u]:
                if d + c < dist.get(v, math.inf):
                    dist[v], prev[v] = d + c, u
                    heapq.heappush(q, (d + c, v))
        out = [b]
        while out[-1] != a:
            out.append(prev[out[-1]])
        return out[::-1]

    def route(p, to):
        zs = [pos[i][2] for i in p]
        passages = []
        for i in p:
            t = g['passages'][g['passage'][i]] if g['passage'][i] >= 0 else None
            if t and (not passages or passages[-1] != t):
                passages.append(t)
        return (to, length(p), sum(max(0, b - a) for a, b in zip(zs, zs[1:])),
                sum(max(0, a - b) for a, b in zip(zs, zs[1:])), list(dict.fromkeys(passages)))

    def length(p):
        return sum(math.dist(pos[a], pos[b]) for a, b in zip(p, p[1:]))
    ents = [n['t'] for n in scene['names'] if n.get('entrance') and not n.get('apart')]
    places = [n['t'] for n in scene['names'] if not n.get('entrance') and not n.get('apart')]
    plan = {'Entrance': ROUTES}
    for e in ents:
        if e != 'Entrance':
            near = [(length(path(node[e], node[t])), t) for t in places]
            plan[e] = [t for d, t in sorted(near) if NEAR < d < length(path(node['Entrance'], node[t]))]
    res = {}
    for frm, tos in plan.items():
        res[frm] = []
        for to in tos:
            if to not in node:
                print(f'no place {to!r}', file=sys.stderr)
                continue
            res[frm].append(route(path(node[frm], node[to]), to))
    return res


def page(scene, rts, preview):
    e = html.escape
    st = scene['stats']
    link = lambda frm, to: f'3d/#from={frm.replace(" ", "%20")}&amp;to={to.replace(" ", "%20")}'
    km = lambda m: f'{m / 1000:.1f} km' if m >= 1000 else f'{round(m)} m'
    card = lambda frm, to, L, up, dn, ps: f'''  <a class="card route" href="{link(frm, to)}">
    <div class="body"><h3>{e(frm)} &rarr; {e(to)}</h3>
    <p class="nums"><b>{km(L)}</b> &middot; up {round(up)} m, down {round(dn)} m</p>
    {f"<p>{'&hellip; ' if len(ps) > 5 else 'Through '}{e(', '.join(ps[:-1][-4:]))}</p>" if ps[:-1] else ''}</div>
  </a>'''
    sections = '\n\n'.join(
        f'''<h2>Routes from {'the entrance' if frm == 'Entrance' else e(frm)}</h2>
<div class="grid">
{chr(10).join(card(frm, *r) for r in rs)}
</div>''' + (f'\n<p class="sub" style="margin-top:14px">{e(NOTES[frm])}</p>' if frm in NOTES else '')
        for frm, rs in rts.items() if rs)
    sizes = {f: os.path.getsize(os.path.join('survey', f)) for f, _, _ in DATA}
    mb = lambda n: f'{n / 1e6:.1f} MB' if n >= 1e6 else f'{n / 1e3:.0f} kB'
    data_rows = '\n'.join(f'<tr><td><a href="data/{f}">{f}</a></td><td>{e(t)}</td><td>{e(d)}</td><td class="n">{sizes[f] / 1e3:.0f} kB</td></tr>'
                          for f, t, d in DATA)
    hero = (f'<a class="hero" href="3d/"><img src="3d/preview.png" alt="Ogof Draenen in 3D beneath the ground surface"></a>'
            if preview else '')
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ogof Draenen route planner</title>
<meta name="description" content="Ogof Draenen, Pwll Du, Blaenavon: the survey in 3D beneath the ground, with turn-by-turn routes through the cave that work offline underground.">
<meta property="og:title" content="Ogof Draenen route planner">
<meta property="og:description" content="The survey in 3D beneath the ground, with turn-by-turn routes through the cave.">
{'<meta property="og:image" content="3d/preview.png">' if preview else ''}
<link rel="icon" href="3d/icon-192.png">
<link rel="stylesheet" href="3d/vendor/inter/inter.css">
<style>
  :root {{ --bg:#ffffff; --fg:#1a1d22; --muted:#5a6068; --line:#e2e5e9; --card:#fbfcfd; --accent:#2f6f7e; --gold:#b07a14; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#14171a; --fg:#e8eaed; --muted:#9aa3ad; --line:#2a2f35; --card:#1b1f23; --accent:#7fc3d3; --gold:#e3b456; }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--fg); font:16px/1.55 Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
  .wrap {{ max-width:1100px; margin:0 auto; padding:48px 24px 80px; }}
  header {{ border-bottom:2px solid var(--fg); padding-bottom:18px; margin-bottom:8px; }}
  h1 {{ font-size:44px; font-weight:600; margin:0 0 6px; letter-spacing:-.5px; }}
  .sub {{ color:var(--muted); margin:0; }}
  .meta {{ display:flex; flex-wrap:wrap; gap:28px; padding:16px 0 28px; border-bottom:1px solid var(--line); margin:0 0 32px; }}
  .meta div {{ min-width:110px; }}
  .meta dt {{ font-size:11px; letter-spacing:.09em; text-transform:uppercase; color:var(--muted); margin:0 0 3px; }}
  .meta dd {{ margin:0; font-size:17px; }}
  .hero {{ display:block; border-radius:12px; overflow:hidden; border:1px solid var(--line); background:#05070c; }}
  .hero img {{ display:block; width:100%; height:auto; }}
  .open {{ display:inline-block; margin:18px 0 0; padding:12px 20px; border-radius:10px; background:var(--accent); color:#fff;
    font-weight:600; text-decoration:none; }}
  .open:hover {{ filter:brightness(1.1); }}
  .open.alt {{ background:transparent; color:var(--accent); border:1px solid var(--accent); margin-left:10px; }}
  .open.alt span {{ color:var(--muted); font-weight:400; }}
  .plan {{ display:block; border-radius:12px; overflow:hidden; border:1px solid var(--line); background:#fff; }}
  .plan img {{ display:block; width:100%; height:auto; }}
  @media (max-width:640px) {{ .open.alt {{ margin-left:0; }} }}
  h2 {{ font-size:12px; letter-spacing:.11em; text-transform:uppercase; color:var(--muted); font-weight:600; margin:48px 0 16px; }}
  .grid {{ display:grid; gap:18px; grid-template-columns:repeat(auto-fill, minmax(300px, 1fr)); }}
  .card {{ border:1px solid var(--line); border-radius:10px; background:var(--card); display:block; color:inherit; text-decoration:none;
    transition:border-color .15s, transform .15s; }}
  .card:hover {{ border-color:var(--accent); transform:translateY(-2px); }}
  .card .body {{ padding:14px 16px 16px; }}
  .card h3 {{ margin:0 0 4px; font-size:17px; font-weight:600; }}
  .card p {{ margin:0; color:var(--muted); font-size:14px; }}
  .card p.nums {{ color:var(--fg); margin-bottom:4px; font-variant-numeric:tabular-nums; }}
  .card p.nums b {{ color:var(--gold); }}
  .feat {{ display:grid; gap:18px 28px; grid-template-columns:repeat(auto-fill, minmax(300px, 1fr)); }}
  .feat h3 {{ margin:0 0 4px; font-size:16px; }}
  .feat p {{ margin:0; color:var(--muted); font-size:15px; }}
  table {{ width:100%; border-collapse:collapse; font-size:15px; }}
  th, td {{ text-align:left; padding:9px 12px 9px 0; border-bottom:1px solid var(--line); vertical-align:top; }}
  th {{ font-size:11px; letter-spacing:.09em; text-transform:uppercase; color:var(--muted); font-weight:600; }}
  td.n {{ font-variant-numeric:tabular-nums; white-space:nowrap; color:var(--muted); }}
  a {{ color:var(--accent); }}
  .credits {{ color:var(--muted); font-size:14px; }}
  .credits li {{ margin:4px 0; }}
  .warn {{ border-left:3px solid var(--gold); padding:4px 0 4px 14px; color:var(--muted); font-size:15px; }}
  footer {{ margin-top:56px; padding-top:18px; border-top:1px solid var(--line); color:var(--muted); font-size:13px; }}
  @media (max-width:640px) {{ h1 {{ font-size:32px; }} .wrap {{ padding:28px 16px 60px; }} }}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>Ogof Draenen</h1>
  <p class="sub">Pwll Du, Blaenavon, South Wales &middot; the survey in 3D beneath the ground, with turn-by-turn routes through the cave</p>
</header>
<dl class="meta">
  <div><dt>Surveyed</dt><dd>{km(st['length'])}</dd></div>
  <div><dt>Vertical range</dt><dd>{st['depth']} m</dd></div>
  <div><dt>Entrance</dt><dd>{e(scene['grid_ref'])}</dd></div>
  <div><dt>Survey data</dt><dd>OUCC Grade 2 and newer</dd></div>
  <div><dt>Built</dt><dd>{e(scene['built'])}</dd></div>
</dl>

{hero}
<a class="open" href="3d/">Open the 3D view and route planner &rarr;</a>
<a class="open alt" href="data/draenen-plan.pdf">The plan <span>PDF, {mb(sizes['draenen-plan.pdf'])}</span></a>
<a class="open alt" href="data/draenen.3d" download>The survey <span>.3d for Aven, {mb(sizes['draenen.3d'])}</span></a>

{sections}
<p class="sub" style="margin-top:14px">Or pick any two places in the 3D view: <b>Routes</b>, under the title.</p>

<h2>Using it</h2>
<div class="feat">
  <div><h3>Turn by turn</h3><p>The shortest way through the survey between any two places, step by step: each junction from above, which way to turn, up or down, where the ways not taken lead, steep drops and the passages entered.</p></div>
  <div><h3>The height of the way</h3><p>A profile of the whole route, and a curtain hung from it in 3D, so the climbs and drops show from any angle.</p></div>
  <div><h3>Underground, offline</h3><p>Open it once with a signal and it's saved on the phone (the chip under the title says <i>Works offline</i>). Add it to the home screen as an app. It only draws when something changes, to save battery.</p></div>
  <div><h3>On a phone</h3><p>The route is a sheet to pull up or down. Swipe the step card to move on. Tap the compass for compass mode: the survey turns as you do. Lost? <i>I'm somewhere else</i> re-routes from where you are.</p></div>
  <div><h3>On paper</h3><p>Print the route as a card: a plan with the steps numbered, the profile, and every junction with its directions. Take it with you.</p></div>
  <div><h3>In 3D</h3><p>The cave beneath the Welsh Government's LiDAR ground and satellite imagery. Scroll on through the passages, double-click to look somewhere, drag the compass to turn and tilt.</p></div>
</div>
<p class="warn">The directions are worked out from the survey's centreline, mostly OUCC's coarse Grade 2 survey with long legs, so treat them as a guide to the shape of the way, not a description of the passage. Never depend on a phone underground.</p>

<h2>The plan</h2>
<a class="plan" href="data/draenen-plan.pdf"><img src="plan.jpg" alt="Part of the plan: the passages coloured by altitude, from purple (high) to green (low), with their names"></a>
<p class="sub" style="margin-top:12px">The survey at 1:5000, coloured by altitude so passages crossing each other stand apart, with the passage names and the entrances: <a href="data/draenen-plan.pdf">the plan (PDF, {mb(sizes['draenen-plan.pdf'])})</a>, for printing or for a phone.</p>

<h2>The data</h2>
<table>
<tr><th>File</th><th>What</th><th></th><th>Size</th></tr>
{data_rows}
</table>
<p class="sub" style="margin-top:12px">Built by Therion from the survey in <a href="{REPO}">{REPO.split('github.com/')[1]}</a>: the <a href="{OUCC}">Oxford University Cave Club's Grade 2 survey data</a> (freely downloadable on condition that the source is acknowledged) and newer surveys, with the code that makes this site.</p>

<h2>Credits</h2>
<ul class="credits">
  <li><b>Survey:</b> Ogof Draenen survey data, Oxford University Cave Club and the many clubs and cavers who surveyed the cave (named in the survey files), <a href="{OUCC}">oucc.org.uk</a>; newer surveys by the teams named in them; compiled in Therion by Rich Smith, <a href="{REPO}">{REPO.split('github.com/')[1]}</a>.</li>
  <li><b>Ground:</b> Welsh Government LiDAR 2020&ndash;22, &copy; Welsh Government, <a href="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/">Open Government Licence v3</a>.</li>
  <li><b>Imagery:</b> &copy; Esri, Maxar, Earthstar Geographics and the GIS User Community.</li>
  <li><b>Software:</b> <a href="https://threejs.org/">three.js</a> (MIT) and the <a href="https://rsms.me/inter/">Inter</a> font (SIL Open Font Licence). The 3D view started as the one made for the <a href="https://github.com/CaveSurveying/uk_mendips_swildons-hole">Swildons Hole survey</a>.</li>
</ul>
<footer>Built {e(scene['built'])} from <a href="{REPO}">{REPO.split('github.com/')[1]}</a>.</footer>
</div>
</body>
</html>
'''


def main():
    os.makedirs(OUT, exist_ok=True)
    build_3d(os.path.join(OUT, '3d'), os.environ.get('CHROMIUM'))
    os.makedirs(os.path.join(OUT, 'data'), exist_ok=True)
    for f, _, _ in DATA:
        shutil.copy(os.path.join('survey', f), os.path.join(OUT, 'data', f))
    shutil.copy(os.path.join('images', 'plan.jpg'), os.path.join(OUT, 'plan.jpg'))   # a part of the plan, for the landing page
    scene = json.load(open(os.path.join(OUT, '3d', 'scene.json')))
    rts = routes(scene)
    preview = os.path.exists(os.path.join(OUT, '3d', 'preview.png'))
    with open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(page(scene, rts, preview))
    print(f'site written to {OUT}/: {sum(map(len, rts.values()))} routes, preview {"yes" if preview else "no (set CHROMIUM)"}', file=sys.stderr)


if __name__ == '__main__':
    main()
