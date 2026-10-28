"""Names on the plan: passage names and the entrances, for Therion.

    python3 -m tools.plannames            # survey/names.th, from survey/draenen.3d
    python3 -m tools.plannames --empty    # survey/names.th with no names

Most of the cave is Grade 2 centreline, with no drawing to put a passage
name in, so each name gets a scrap of its own: a station (the one nearest
the middle of the passage's surveys, as in the 3D view, from
tools/names.py) and the name on it, as a remark (the drawings' own
labels are hidden at this scale), and each entrance its entrance symbol.
The map names-plan@draenen holds them all, and the plan includes it.

The stations come from the built survey, so names.th is written from the
last build and the survey is built again (as CI does: --empty, therion,
this, therion). It's committed, so the survey builds without it being
made first; make it again when the names or the surveys change.
"""
import argparse
import sys

from tools.model3d.__main__ import place_names
from tools.model3d.formats import read_3d
from tools.names import ENTRANCE, SURVEY, Names, survey_ids

OUT = 'survey/names.th'
SCALE = 'xl'      # the size of the names on the plan
# how much of the plan a name of that size covers, in metres at 1:5000
# (for leaving out the names that would overlap others)
CHAR, LINE = 9.0, 14.0


def ref(station, surveys):
    """A station in the .3d (draenen.area.section.file.stn) as Therion
    refers to it from inside the survey draenen (stn@file.section.area).
    The Grade 2 station names can have dots in them too (s8.2, 3.1), so
    below the file the survey path is the parts declared as surveys in that
    file, and the rest is the station."""
    parts = station.split('.')[1:]
    k = min(3, len(parts) - 1)
    inside = surveys.get(parts[2], set()) if k == 3 else set()
    while k < len(parts) - 1 and parts[k] in inside:
        k += 1
    stn = '.'.join(parts[k:])
    return f'{stn}@{".".join(reversed(parts[:k]))}' if k else stn


def quote(t):
    return t.replace('"', "'")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--empty', action='store_true', help='no names (for the first build)')
    args = ap.parse_args()
    surveys = survey_ids()
    # with no names, the entrance alone (Therion won't have an empty map)
    scraps = [(ENTRANCE, ['point 0 0 entrance'])] if args.empty else []
    if not args.empty:
        legs, stations = read_3d(SURVEY)
        names = Names(stations)
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
            t += ' (tie provisional)' if provisional else ''
            free(at[n], t, 8)
            scraps.append((n, ['point 0 0 entrance', f'point 8 0 remark -text "{quote(t)}" -scale {SCALE} -align r']))
        places = [x for x in place_names(stations, names) if x[0] not in {e[1] for e in ents}]
        for t, n, p in sorted(places, key=lambda x: (names.station(x[1]) is None, -size.get(x[0], 0))):
            if free(p, t):
                scraps.append((n, [f'point 0 0 remark -text "{quote(t)}" -scale {SCALE}']))
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('encoding  utf-8\n\n# Made by python3 -m tools.plannames from survey/names.json: '
                'passage names and entrances for the plan. Edit names.json, not this.\n\n')
        for k, (n, points) in enumerate(scraps):
            f.write(f'scrap name-{k} -projection plan -scale [0 0 1 0 0 0 1 0 m]\n'
                    f'  point 0 0 station -name {ref(n, surveys)}\n' + ''.join(f'  {p}\n' for p in points) + 'endscrap\n\n')
        f.write('map names-plan -proj plan\n' + ''.join(f'  name-{k}\n' for k in range(len(scraps))) + 'endmap\n')
    print(f'{OUT}: {len(scraps)} names', file=sys.stderr)


if __name__ == '__main__':
    main()
