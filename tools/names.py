"""The survey as the tools see it: where Therion writes it, how it's put on
the National Grid, and the names of its passages, entrances and junctions.

The names are in survey/names.json:

passages   by survey file (the Grade 2 survey names, as in
           draenen.<area>.<section>.<file>.<station>), so one name covers
           all its stations. A file split into parts (canyon_e, canyon_s)
           takes the name of the part before the "_". A section none of
           whose files has a name is named by its -title in the .th files.
stations   single stations by name (the junctions between sections).
entrances  the stations flagged as entrances in the survey, by station;
           "provisional" for one whose tie into the cave isn't known yet
           (it's shown, but not offered for routes).
"""
import glob
import json
import os
import re

SURVEY = 'survey/draenen.3d'
NAMES = 'survey/names.json'
ENTRANCE = 'draenen.entrance.entrance-series.entrance.0'
# The survey is in its own local coordinates, with the entrance at 0 0 0.
# OUCC fixed the same station at this point on the National Grid, in the SO
# 100 km square, in their processed survey (OD2.3d, 2003); moving the survey
# there puts it on the grid without touching its shape.
FIX = (24650.0, 11750.0, 380.0)


def file_of(station):
    """The survey file a station is in (draenen.<area>.<section>.<file>...)."""
    parts = station.split('.')
    return parts[3] if len(parts) >= 5 else None


def section_of(station):
    parts = station.split('.')
    return parts[2] if len(parts) >= 4 else None


def titles(root='survey'):
    """{survey: -title} from the .th files."""
    out = {}
    for path in glob.glob(os.path.join(root, '**', '*.th'), recursive=True):
        for m in re.finditer(r'^\s*survey\s+(\S+)\s+.*?-title\s+"([^"]*)"', open(path, encoding='utf-8').read(), re.M):
            out.setdefault(m[1], m[2])
    return out


def survey_ids(root='survey'):
    """{survey: the surveys declared in the same .th file}, so the surveys
    inside one (a Grade 2 file's sections) can be told from its stations."""
    out = {}
    for path in glob.glob(os.path.join(root, '**', '*.th'), recursive=True):
        ids = re.findall(r'^\s*survey\s+(\S+)', open(path, encoding='utf-8').read(), re.M)
        for i in ids:
            out.setdefault(i, set()).update(ids)
    return out


def on_grid(legs, stations):
    """The survey moved so the entrance is at FIX."""
    e = next(p for n, p, f in stations if n == ENTRANCE)
    d = [FIX[k] - e[k] for k in range(3)]

    def mv(p):
        return (round(p[0] + d[0], 2), round(p[1] + d[1], 2), round(p[2] + d[2], 2))
    return [(mv(a), mv(b), f) for a, b, f in legs], [(n, mv(p), f) for n, p, f in stations]


class Names:
    def __init__(self, stations, path=NAMES):
        j = json.load(open(path, encoding='utf-8'))
        self.passages = j['passages']
        self.stations = j.get('stations', {})
        self.entrances = j.get('entrances', {})
        named = {section_of(n) for n, p, f in stations if self._file_name(file_of(n))}
        t = titles()
        # (not a title that's a stretch of the way, "Cairn Junction to Tea Junction")
        self.sections = {s: t[s] for s in {section_of(n) for n, p, f in stations if file_of(n)} - named
                         if s in t and ' to ' not in t[s]}

    def _file_name(self, f):
        return f and (self.passages.get(f) or self.passages.get(f.split('_')[0]))

    def passage(self, station):
        """The passage name of a station, or None."""
        return self._file_name(file_of(station)) or self.sections.get(section_of(station))

    def station(self, station):
        """The name of a named single station (a junction), or None."""
        return self.stations.get(station.split('.')[-1])

    def entrance(self, station):
        """(name, provisional) for an entrance station."""
        e = self.entrances.get(station, {})
        return e.get('name', 'Entrance'), bool(e.get('provisional'))
