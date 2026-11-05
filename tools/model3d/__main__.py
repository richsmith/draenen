"""The 3D view: Ogof Draenen in 3D beneath the ground surface, by cave-viewer.

    python3 -m tools.model3d      # writes site/3d/ (tools.site runs it)

The page and its build are cave-viewer's
(https://github.com/CaveSurveying/cave-viewer, pinned in
tools/model3d/requirements.txt), configured by caves.json: the centreline
from survey/draenen.3d (the survey as Therion builds it: therion
survey/draenen.thconfig), put on the National Grid at OUCC's fixed point
for the entrance (grid.fix), and the Welsh Government's 1 m LiDAR, kept,
averaged, in lidar/. This step writes the names of passages, entrances and
junctions from survey/names.json (tools/names.py) in cave-viewer's terms
(build/cave-viewer/draenen-names.json), then runs it. With CHROMIUM set it
also saves a preview.png.
"""
import json
import math
import os
import re
import subprocess
import sys

from tools.model3d.formats import read_3d
from tools.names import ENTRANCE, SURVEY, Names, file_of, section_of

CONFIG = 'caves.json'
NAMES = 'build/cave-viewer/draenen-names.json'


def place_names(stations, names):
    """One label per passage name, at the station nearest the middle of
    all its surveys, and one at each named junction: (name, station, xyz)."""
    by, out, seen = {}, [], set()
    for n, p, f in stations:
        t = names.passage(n)
        if t:
            by.setdefault(t, []).append((n, p))
    for t, ps in by.items():
        mx, my = sum(p[0] for n, p in ps) / len(ps), sum(p[1] for n, p in ps) / len(ps)
        n, p = min(ps, key=lambda s: math.hypot(s[1][0] - mx, s[1][1] - my))
        out.append((t, n, p))
    for n, p, f in sorted(stations, key=lambda s: len(s[0])):
        t = names.station(n)
        if t and t not in seen and t not in by:
            seen.add(t)
            out.append((t, n, p))
    return out


def write_names(path=NAMES):
    """survey/names.json, in cave-viewer's terms: the entrances (the main one
    first; a provisional one shown but kept out of the routes, as apart), the
    passages by survey file and section as patterns of station names (codes),
    and a label for each passage and named junction at a station (places,
    which name no stations near them: alone)."""
    legs, stations = read_3d(SURVEY)
    names = Names(stations)
    ents = {n: names.entrance(n) for n, p, f in sorted((s for s in stations if s[2] & 4), key=lambda s: s[0] != ENTRANCE)}
    skip = {t for t, prov in ents.values()}          # (a passage named as an entrance is labelled by the entrance)
    codes, sections = {}, {}
    for n, p, f in stations:
        sec, fil = section_of(n), file_of(n)
        t = names._file_name(fil)
        if t and t not in skip:
            codes[rf'^draenen\.[^.]+\.{re.escape(sec)}\.{re.escape(fil)}\.'] = t
        elif sec in names.sections and names.sections[sec] not in skip:
            sections[rf'^draenen\.[^.]+\.{re.escape(sec)}\.'] = names.sections[sec]
    out = {
        'entrances': {n: t for n, (t, prov) in ents.items()},
        'apart': [t for t, prov in ents.values() if prov],
        'codes': {**codes, **sections},              # (a file's name first, then its section's)
        'places': {t: n for t, n, p in place_names(stations, names) if t not in skip},
    }
    out['alone'] = list(out['places'])               # (labels only: passages are named by their files, as above, not by nearness)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(out, open(path, 'w'), indent=2, ensure_ascii=False)
    print(f'{len(out["places"])} names, {len(out["codes"])} passage patterns for the 3D view', file=sys.stderr)


def build(out_dir, chromium=None):
    """The 3D view in out_dir (its folder in caves.json: site/3d)."""
    write_names()
    env = {**os.environ, **({'CHROMIUM': chromium} if chromium else {})}
    subprocess.run([sys.executable, '-m', 'caveviewer', 'build', CONFIG, '--out', os.path.dirname(os.path.normpath(out_dir)),
                    '--steps', 'survey,model'], check=True, env=env)


def main():
    build(os.path.join('site', '3d'), os.environ.get('CHROMIUM'))


if __name__ == '__main__':
    main()
