"""The plan's colour and names, for Therion.

    python3 -m tools.plan            # survey/plan.th, from survey/draenen.3d
    python3 -m tools.plan --empty    # survey/plan.th with just the entrance

Most of the cave is Grade 2 centreline, with no drawing, and Therion
colours only scraps, not survey lines. So survey/plan.th has two maps of
scraps made from the centreline:

colour-plan  a ribbon a few metres wide along the centreline, cut into
             short pieces, each a scrap pinned to its stations, with an
             outline that isn't drawn: coloured by altitude (colour
             map-fg altitude in the layout), the highest on top, so
             passages crossing each other stand apart. Not where a
             survey has drawings of its own.
names-plan   the passage names, each at the station nearest the middle of
             the passage's surveys (as in the 3D view, from tools/names.py),
             as a remark (the drawings' own labels are hidden at this
             scale), leaving out any that would cover another; and each
             entrance, with its symbol.

The stations come from the built survey, so plan.th is written from the
last build and the survey is built again (as CI does: --empty, therion,
this, therion). It's committed, so the survey builds without it being
made first; make it again when the names or the surveys change.
"""
import argparse
import glob
import math
import os
import re
import sys

from tools.model3d.__main__ import place_names
from tools.model3d.formats import read_3d
from tools.names import ENTRANCE, SURVEY, Names

OUT = 'survey/plan.th'
STATIONS = 'survey/draenen-stations.sql'   # Therion's database of the survey (draenen.thconfig)
ENTRANCE_REF = '0@entrance.entrance-series.entrance'
SCALE = 'xl'      # the size of the names on the plan
# how much of the plan a name of that size covers, in metres at 1:5000
# (for leaving out the names that would overlap others)
CHAR, LINE = 9.0, 14.0
WIDTH = 7.0       # the ribbon's width, metres (1.4 mm at 1:5000)
PIECE = 40.0      # the longest piece of ribbon, metres, so its colour follows the altitude


def refs(path=STATIONS):
    """{station as in the .3d (draenen.area.section.file.stn): as Therion
    refers to it from inside the survey draenen (stn@file.section.area)},
    from Therion's database of the survey. (The .3d's names can't be split
    by themselves: the Grade 2 station names have dots in them too, s8.2.)"""
    sql = open(path, encoding='utf-8').read()
    surveys = {int(i): full for i, full in re.findall(r"insert into SURVEY values \((\d+), \d+, '[^']*', '([^']*)'", sql)}
    out = {}
    for name, sid in re.findall(r"insert into STATION values \(\d+, '([^']*)', (\d+),", sql):
        full = surveys.get(int(sid), '')
        if full == 'draenen' or full.endswith('.draenen'):
            path = full[:-len('draenen')].rstrip('.')
            out['.'.join(['draenen', *reversed(path.split('.'))] if path else ['draenen']) + '.' + name] = f'{name}@{path}' if path else name
    return out


def quote(t):
    return t.replace('"', "'")


def drawn_surveys(root='survey'):
    """The surveys with drawings: those in a .th file beside a .th2."""
    out = set()
    for path in glob.glob(os.path.join(root, '**', '*.th'), recursive=True):
        if glob.glob(os.path.join(os.path.dirname(path), '*.th2')):
            out.update(x.strip('"') for x in re.findall(r'^\s*survey\s+(\S+)', open(path, encoding='utf-8').read(), re.M))
    return out


def pieces(legs, stations, skip):
    """The centreline in pieces: runs of legs between junctions and ends,
    cut at PIECE metres, each [(station or None, xyz)]."""
    key = lambda p: (round(p[0] * 100), round(p[1] * 100), round(p[2] * 100))
    name = {}
    for n, p, f in sorted(stations, key=lambda s: len(s[0])):
        name.setdefault(key(p), n)
    adj, pos = {}, {}
    for a, b, f in legs:
        if f & 7:                       # surface, duplicate, splay
            continue
        ka, kb = key(a), key(b)
        if ka == kb or any(skip & set(name.get(k, '').split('.')[:-1]) for k in (ka, kb)):
            continue
        pos[ka], pos[kb] = a, b
        adj.setdefault(ka, set()).add(kb)
        adj.setdefault(kb, set()).add(ka)
    done, runs = set(), []

    def walk(k, nxt):
        run = [k]
        while (k, nxt) not in done:
            done.update({(k, nxt), (nxt, k)})
            run.append(nxt)
            k, nxt = nxt, next((x for x in adj[nxt] if (nxt, x) not in done), None) if len(adj[nxt]) == 2 else None
            if nxt is None:
                break
        runs.append(run)
    for k in adj:
        if len(adj[k]) != 2:
            for n in adj[k]:
                if (k, n) not in done:
                    walk(k, n)
    for k in adj:                       # what's left are loops
        for n in adj[k]:
            if (k, n) not in done:
                walk(k, n)
    out = []
    for run in runs:
        cur, d = [run[0]], 0.0
        for a, b in zip(run, run[1:]):
            d += math.dist(pos[a][:2], pos[b][:2])
            cur.append(b)
            if d >= PIECE:
                out.append(cur)
                cur, d = [b], 0.0
        if len(cur) > 1:
            out.append(cur)
    return [[(name.get(k), pos[k]) for k in piece] for piece in out]


def ribbon(pts, w=WIDTH):
    """The outline of a ribbon w wide along a path in plan: one side out, the
    other back, carried on half its width past each end, so the pieces
    overlap where they meet."""
    def past(p, q):
        L = math.dist(p, q) or 1
        return (p[0] + (p[0] - q[0]) / L * w / 2, p[1] + (p[1] - q[1]) / L * w / 2)
    pts = [past(pts[0], pts[1]), *pts[1:-1], past(pts[-1], pts[-2])]
    left, right = [], []
    for i, p in enumerate(pts):
        a, b = pts[max(0, i - 1)], pts[min(len(pts) - 1, i + 1)]
        t = (b[0] - a[0], b[1] - a[1])
        L = math.hypot(*t) or 1
        nx, ny = -t[1] / L, t[0] / L
        # mitred through the bends, so the ribbon keeps its width
        m = 1
        if 0 < i < len(pts) - 1:
            u = (p[0] - a[0], p[1] - a[1])
            lu = math.hypot(*u)
            if lu:
                m = 1 / max(0.5, (u[0] * t[0] + u[1] * t[1]) / (lu * L))
        h = w / 2 * m
        left.append((p[0] + nx * h, p[1] + ny * h))
        right.append((p[0] - nx * h, p[1] - ny * h))
    return left + right[::-1]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--empty', action='store_true', help='just the entrance (for the first build)')
    args = ap.parse_args()
    ref = {ENTRANCE: ENTRANCE_REF} if args.empty else refs()
    # with nothing built yet, the entrance alone (Therion won't have an empty map)
    names_scraps = [(ENTRANCE, ['point 0 0 entrance'])] if args.empty else []
    colour_scraps = [f'  point 0 0 station -name {ref[ENTRANCE]}\n'] if args.empty else []
    if not args.empty:
        legs, stations = read_3d(SURVEY)
        names = Names(stations)

        # the ribbon, from the lowest piece to the highest, so the higher are on top
        for piece in sorted(pieces(legs, stations, drawn_surveys()), key=lambda pc: sum(p[2] for n, p in pc) / len(pc)):
            pts = [p for n, p in piece]
            stns = list(dict.fromkeys(n for n, p in piece if n in ref))
            if not stns:
                continue
            outline = ''.join(f'    {x:.2f} {y:.2f}\n' for x, y in ribbon([p[:2] for p in pts]))
            colour_scraps.append(''.join(f'  point {p[0]:.2f} {p[1]:.2f} station -name {ref[n]}\n'
                                         for n, p in dict((n, p) for n, p in piece if n in ref).items())
                                 + f'  line wall -close on -visibility off\n{outline}  endline\n')

        ents = [(n, *names.entrance(n)) for n, p, f in stations if f & 4]
        at = {n: p for n, p, f in stations}
        size = {}
        for n, p, f in stations:
            size[names.passage(n)] = size.get(names.passage(n), 0) + 1
        # the entrances first, by the symbol; then the junctions, and the
        # passages from the longest, each left out if it would cover another
        taken = []

        def free(p, t, dx=0.0):
            w = CHAR * len(t)
            box = (p[0] + dx - (0 if dx else w / 2), p[1] - LINE / 2, p[0] + dx + (w if dx else w / 2), p[1] + LINE / 2)
            if any(box[0] < b[2] and box[2] > b[0] and box[1] < b[3] and box[3] > b[1] for b in taken):
                return False
            taken.append(box)
            return True
        for n, t, provisional in ents:
            if n not in ref:
                continue
            t += ' (tie provisional)' if provisional else ''
            free(at[n], t, 8)
            names_scraps.append((n, ['point 0 0 entrance', f'point 8 0 remark -text "{quote(t)}" -scale {SCALE} -align r']))
        places = [x for x in place_names(stations, names) if x[0] not in {e[1] for e in ents}]
        for t, n, p in sorted(places, key=lambda x: (names.station(x[1]) is None, -size.get(x[0], 0))):
            if n in ref and free(p, t):
                names_scraps.append((n, [f'point 0 0 remark -text "{quote(t)}" -scale {SCALE}']))
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('encoding  utf-8\n\n# Made by python3 -m tools.plan from the built survey and survey/names.json: '
                'the coloured ribbon, the passage names and the entrances for the plan. Edit names.json, not this.\n\n')
        for k, body in enumerate(colour_scraps):
            f.write(f'scrap colour-{k} -projection plan -scale [0 0 1 0 0 0 1 0 m]\n{body}endscrap\n\n')
        for k, (n, points) in enumerate(names_scraps):
            f.write(f'scrap name-{k} -projection plan -scale [0 0 1 0 0 0 1 0 m]\n'
                    f'  point 0 0 station -name {ref[n]}\n' + ''.join(f'  {p}\n' for p in points) + 'endscrap\n\n')
        f.write('map colour-plan -proj plan\n' + ''.join(f'  colour-{k}\n' for k in range(len(colour_scraps))) + 'endmap\n\n')
        f.write('map names-plan -proj plan\n' + ''.join(f'  name-{k}\n' for k in range(len(names_scraps))) + 'endmap\n')
    print(f'{OUT}: {len(colour_scraps)} pieces of ribbon, {len(names_scraps)} names', file=sys.stderr)


if __name__ == '__main__':
    main()
