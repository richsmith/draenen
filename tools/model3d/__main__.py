"""The 3D view: Ogof Draenen in 3D beneath the ground surface.

    python3 -m tools.model3d      # writes site/3d/ (index.html, scene.json, terrain.bin, ...)

Reads the centreline and stations from survey/draenen.3d (the survey as
Therion builds it: therion survey/draenen.thconfig), put on the National
Grid at OUCC's fixed point for the entrance, and the names of passages,
entrances and junctions from survey/names.json (tools/names.py). The
centreline also goes in as a graph, which the page finds routes through. The
ground is the Welsh Government's 1 m LiDAR terrain model (2020-22),
fetched once tile by tile and kept, averaged, in lidar/. The satellite
imagery is loaded by the page itself, from Esri.

With CHROMIUM set to a Chrome or Chromium binary it also saves a
preview.png.
"""
import argparse
import array
import datetime
import gzip
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import urllib.parse
import urllib.request
import zlib

from tools.model3d.formats import read_3d, read_tiff
from tools.names import ENTRANCE, SURVEY, Names, file_of, on_grid

HERE = os.path.dirname(os.path.abspath(__file__))
# The survey is put in the SO 100 km square of the National Grid (tools/names.py):
# add these to get full grid references.
SO = (300000, 200000)
# The Welsh Government's LiDAR tile catalogue: 1 km tiles, each with a link
# to its 1 m DTM as a GeoTIFF.
WFS = ('https://datamap.gov.wales/geoserver/ows?service=WFS&version=2.0.0&request=GetFeature'
       '&typeNames=geonode:welsh_government_lidar_tile_catalogue_2020_2023&outputFormat=application/json'
       '&bbox={e0},{n0},{e1},{n1},EPSG:27700')
UA = 'caves-wales-draenen 3D view'
MARGIN = 250      # metres of ground around the cave
STEP = 4          # metres between terrain samples in the model (a multiple of the 1 m LiDAR)
TILE = 1000       # the LiDAR tiles are 1 km squares


# -- the ground -----------------------------------------------------------------------

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    return urllib.request.urlopen(req, timeout=180).read()


def lidar(e0, n0, e1, n1, cache='lidar'):
    """Ground heights over a National Grid box, every STEP metres from the
    top-left corner, as (columns, rows, heights in centimetres, 0 where
    there is no LiDAR). Fetched from the Welsh Government the first time,
    1 km tile by tile, and kept averaged."""
    w, h = (e1 - e0) // STEP, (n1 - n0) // STEP
    f = os.path.join(cache, f'dtm-{e0}-{n0}-{e1}-{n1}-{STEP}m.u16.gz')
    if not os.path.exists(f):
        total, count = array.array('d', bytes(8 * w * h)), array.array('H', bytes(2 * w * h))
        tiles = json.loads(get(WFS.format(e0=e0, n0=n0, e1=e1, n1=n1)))['features']
        for k, t in enumerate(tiles):
            link = t['properties']['dtm_link']
            url = link if link.startswith('http') else 'https://' + urllib.parse.quote(link)
            print(f'fetching LiDAR tile {t["properties"]["british_gr"]} ({k + 1} of {len(tiles)})', file=sys.stderr)
            tw, th, v, (x0, y0), px = read_tiff(get(url))
            if px != 1.0:
                raise ValueError(f'unexpected LiDAR pixel size {px} m in {url}')
            x0, y0 = round(x0), round(y0)
            for r in range(th):
                j = (n1 - (y0 - r)) // STEP        # the model row this LiDAR row falls in
                if not 0 <= j < h:
                    continue
                row = r * tw
                for c in range(tw):
                    i = (x0 + c - e0) // STEP
                    z = v[row + c]
                    if 0 <= i < w and z > -1000:
                        total[j * w + i] += z
                        count[j * w + i] += 1
        out = array.array('H', (round(t / n * 100) if n else 0 for t, n in zip(total, count)))
        if sys.byteorder != 'little':
            out.byteswap()
        os.makedirs(cache, exist_ok=True)
        with gzip.open(f, 'wb') as g:
            g.write(out.tobytes())
    raw = array.array('H', gzip.open(f).read())
    if sys.byteorder != 'little':
        raw.byteswap()
    return w, h, raw


# -- National Grid to lat/long ----------------------------------------------------------

def grid_to_ll(e, n):
    """OSGB36 National Grid to WGS84 lat/long (degrees), by the Ordnance
    Survey's formulae and a Helmert shift: good to a few metres, and the
    caller corrects what is left with the entrance's OSTN15 position."""
    a, b, f0 = 6377563.396, 6356256.909, 0.9996012717
    lat0, lon0, e0, n0 = math.radians(49), math.radians(-2), 400000, -100000
    e2 = 1 - b * b / (a * a)
    nn = (a - b) / (a + b)
    lat, m = lat0, 0
    while abs(n - n0 - m) >= 1e-5:
        lat += (n - n0 - m) / (a * f0)
        m = b * f0 * ((1 + nn + 1.25 * nn ** 2 + 1.25 * nn ** 3) * (lat - lat0)
                      - (3 * nn + 3 * nn ** 2 + 21 / 8 * nn ** 3) * math.sin(lat - lat0) * math.cos(lat + lat0)
                      + (15 / 8 * nn ** 2 + 15 / 8 * nn ** 3) * math.sin(2 * (lat - lat0)) * math.cos(2 * (lat + lat0))
                      - 35 / 24 * nn ** 3 * math.sin(3 * (lat - lat0)) * math.cos(3 * (lat + lat0)))
    s, c, t = math.sin(lat), math.cos(lat), math.tan(lat)
    nu = a * f0 / math.sqrt(1 - e2 * s * s)
    rho = a * f0 * (1 - e2) / (1 - e2 * s * s) ** 1.5
    eta2 = nu / rho - 1
    de = e - e0
    lat = (lat - t / (2 * rho * nu) * de ** 2
           + t / (24 * rho * nu ** 3) * (5 + 3 * t * t + eta2 - 9 * t * t * eta2) * de ** 4
           - t / (720 * rho * nu ** 5) * (61 + 90 * t * t + 45 * t ** 4) * de ** 6)
    lon = (lon0 + de / (c * nu)
           - de ** 3 / (6 * c * nu ** 3) * (nu / rho + 2 * t * t)
           + de ** 5 / (120 * c * nu ** 5) * (5 + 28 * t * t + 24 * t ** 4)
           - de ** 7 / (5040 * c * nu ** 7) * (61 + 662 * t * t + 1320 * t ** 4 + 720 * t ** 6))
    # Airy 1830 to GRS80 through Cartesian coordinates
    s, c = math.sin(lat), math.cos(lat)
    nu = a / math.sqrt(1 - e2 * s * s)
    x, y, z = nu * c * math.cos(lon), nu * c * math.sin(lon), nu * (1 - e2) * s
    tx, ty, tz, sc = 446.448, -125.157, 542.060, -20.4894e-6
    rx, ry, rz = (math.radians(v / 3600) for v in (0.1502, 0.2470, 0.8421))
    x, y, z = (tx + (1 + sc) * x - rz * y + ry * z,
               ty + rz * x + (1 + sc) * y - rx * z,
               tz - ry * x + rx * y + (1 + sc) * z)
    a2, b2 = 6378137.0, 6356752.3141
    e2 = 1 - b2 * b2 / (a2 * a2)
    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1 - e2))
    for _ in range(10):
        lat = math.atan2(z + e2 * a2 / math.sqrt(1 - e2 * math.sin(lat) ** 2) * math.sin(lat), p)
    return math.degrees(lat), math.degrees(math.atan2(y, x))


def mercator(lat, lon):
    """Web Mercator, as a fraction of the world (0..1 across and down)."""
    s = math.sin(math.radians(lat))
    return (lon + 180) / 360, 0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)


def fit_affine(pairs):
    """Least-squares (u, v) = A (1, x, y) over (x, y) -> (u, v) pairs."""
    m = [[0.0] * 3 for _ in range(3)]
    ru, rv = [0.0] * 3, [0.0] * 3
    for (x, y), (u, v) in pairs:
        r = (1.0, x, y)
        for i in range(3):
            ru[i] += r[i] * u
            rv[i] += r[i] * v
            for j in range(3):
                m[i][j] += r[i] * r[j]

    def solve(rhs):
        a = [row[:] + [rhs[i]] for i, row in enumerate(m)]
        for i in range(3):
            p = max(range(i, 3), key=lambda k: abs(a[k][i]))
            a[i], a[p] = a[p], a[i]
            for k in range(3):
                if k != i:
                    f = a[k][i] / a[i][i]
                    a[k] = [x - f * y for x, y in zip(a[k], a[i])]
        return [a[i][3] / a[i][i] for i in range(3)]
    return solve(ru) + solve(rv)


# -- the scene ------------------------------------------------------------------------

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


def graph(legs, stations, names, rel, skip=()):
    """The centreline as a graph for the page's routes. Stations at the same
    place are one node (the old .3d file has no equates, only shared
    positions; Therion's does, but stations at one place are still one
    place). Each node has a station name and, where its survey has
    one, a passage name (not one in skip)."""
    key = lambda p: (round(p[0] * 100), round(p[1] * 100), round(p[2] * 100))
    index, pos, edges = {}, [], set()

    def node(p):
        k = key(p)
        if k not in index:
            index[k] = len(index)
            pos.extend(rel(p))
        return index[k]
    for a, b, f in legs:
        if f & 7:                       # surface, duplicate, splay
            continue
        i, j = node(a), node(b)
        if i != j:
            edges.add((min(i, j), max(i, j)))
    stn, passage, survey = [''] * len(index), [-1] * len(index), [-1] * len(index)
    passage_of = lambda n: (lambda t: t if t not in skip else None)(names.passage(n))
    plist = sorted({t for t in map(passage_of, (n for n, p, f in stations)) if t})
    slist = sorted({file_of(n) or '' for n, p, f in stations})
    for n, p, f in sorted(stations, key=lambda s: len(s[0])):
        i = index.get(key(p))
        if i is None:
            continue
        if not stn[i]:
            stn[i] = n
            survey[i] = slist.index(file_of(n) or '')
        t = passage_of(n)
        if t and passage[i] < 0:
            passage[i] = plist.index(t)
    return {'pos': pos, 'edges': [v for e in sorted(edges) for v in e], 'stn': stn,
            'passage': passage, 'passages': plist, 'survey': survey, 'surveys': slist}


def build(out_dir, chromium=None):
    legs, stations = on_grid(*read_3d(SURVEY))
    cave = [p for a, b, f in legs if not f & 1 for p in (a, b)]
    xs, ys, zs = zip(*cave)

    # the ground: the cave's extent plus a margin, on a 100 m grid (so the
    # model's cells line up with the 1 m LiDAR tiles)
    e0 = int(math.floor((min(xs) + SO[0] - MARGIN) / 100) * 100)
    e1 = int(math.ceil((max(xs) + SO[0] + MARGIN) / 100) * 100)
    n0 = int(math.floor((min(ys) + SO[1] - MARGIN) / 100) * 100)
    n1 = int(math.ceil((max(ys) + SO[1] + MARGIN) / 100) * 100)
    tw, th, heights = lidar(e0, n0, e1, n1)
    # the scene's origin: the middle of the ground, in survey coordinates
    ox, oy = (e0 + e1) / 2 - SO[0], (n0 + n1) / 2 - SO[1]

    # georeference for the imagery: survey x, y (from the origin) to Web Mercator
    pairs = []
    for i in range(5):
        for j in range(5):
            x, y = e0 + (e1 - e0) * i / 4, n0 + (n1 - n0) * j / 4
            pairs.append(((x - SO[0] - ox, y - SO[1] - oy), mercator(*grid_to_ll(x, y))))
    merc = fit_affine(pairs)

    def r(v):
        return round(v, 2)

    def rel(p):
        return [r(p[0] - ox), r(p[1] - oy), r(p[2])]

    kinds = {'legs': [], 'duplicates': [], 'splays': [], 'surface': []}
    for a, b, f in legs:
        k = 'surface' if f & 1 else 'splays' if f & 4 else 'duplicates' if f & 2 else 'legs'
        kinds[k] += rel(a) + rel(b)

    pnames = Names(stations)
    # (a passage named as an entrance is labelled by the entrance)
    ents = {pnames.entrance(n)[0] for n, p, f in stations if f & 4}
    names = [{'t': t, 'p': rel(p)} for t, n, p in place_names(stations, pnames) if t not in ents]
    # the entrances (flagged in the survey), the main one first; one whose
    # tie into the cave is provisional is shown but kept out of the routes
    ent = next((p for n, p, f in stations if n == ENTRANCE), None)
    for n, p, f in sorted((s for s in stations if s[2] & 4), key=lambda s: s[0] != ENTRANCE):
        t, provisional = pnames.entrance(n)
        names.insert(0 if n == ENTRANCE else len(names), {'t': t, 'p': rel(p), 'entrance': True, **({'apart': True} if provisional else {})})

    length = sum(math.dist(a, b) for a, b, f in legs if not f & 7)
    hs = [v / 100 for v in heights if v]
    scene = {
        'title': 'Ogof Draenen',
        'subtitle': 'Pwll Du, Blaenavon',
        'built': datetime.date.today().isoformat(),
        'origin': [ox + SO[0], oy + SO[1]],
        'grid_ref': f'SO {round(ent[0]) if ent else ""} {round(ent[1]) if ent else ""}',
        'stats': {'length': round(length), 'depth': round(max(zs) - min(zs)),
                  'top': r(max(zs)), 'bottom': r(min(zs))},
        'terrain': {'file': 'terrain.bin', 'w': tw, 'h': th, 'step': STEP,
                    'x0': e0 - SO[0] - ox, 'y0': n1 - SO[1] - oy, 'min': min(hs), 'max': max(hs)},
        'merc': merc,
        'walls': {'pos': [], 'idx': []},
        'names': names,
        'graph': graph(legs, stations, pnames, rel, ents),
        **kinds,
    }
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'scene.json'), 'w') as f:
        json.dump(scene, f, separators=(',', ':'))
    with open(os.path.join(out_dir, 'terrain.bin'), 'wb') as f:
        f.write(heights.tobytes())
    shutil.copy(os.path.join(HERE, 'viewer.html'), os.path.join(out_dir, 'index.html'))
    offline(out_dir)
    print(f'3D view written to {out_dir}: {len(legs)} legs, {len(names)} names, '
          f'{length / 1000:.1f} km, ground {tw}x{th} at {STEP} m', file=sys.stderr)
    if chromium:
        preview(chromium, out_dir)


def offline(out_dir):
    """What the page needs to work with no signal: three.js and the font from
    vendor/ (rather than from the internet), the app's manifest and icons, and
    a service worker that keeps all of it, listed and versioned by content."""
    for d in ('vendor',):
        shutil.rmtree(os.path.join(out_dir, d), ignore_errors=True)
        shutil.copytree(os.path.join(HERE, d), os.path.join(out_dir, d))
    for f in os.listdir(os.path.join(HERE, 'static')):
        if f != 'sw.js':
            shutil.copy(os.path.join(HERE, 'static', f), os.path.join(out_dir, f))
    files = ['./']
    for root, dirs, names in os.walk(out_dir):
        dirs[:] = sorted(dirs)
        for n in sorted(names):
            if n in ('sw.js', 'preview.png', '.DS_Store') or n.endswith(('LICENSE', 'LICENSE.txt')):
                continue
            files.append(os.path.relpath(os.path.join(root, n), out_dir).replace(os.sep, '/'))
    h = hashlib.sha256()
    for f in files[1:]:
        h.update(f.encode())
        h.update(open(os.path.join(out_dir, f), 'rb').read())
    sw = open(os.path.join(HERE, 'static', 'sw.js')).read()
    sw = sw.replace("'__VERSION__'", repr(h.hexdigest()[:12])).replace('__FILES__', json.dumps(files, indent=2))
    with open(os.path.join(out_dir, 'sw.js'), 'w') as f:
        f.write(sw)


def preview(chromium, out_dir, port=8765, size=(1200, 750)):
    """A still of the view for the index page, by headless Chrome."""
    import functools
    import http.server
    import threading

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', port), functools.partial(Quiet, directory=out_dir))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    png = os.path.abspath(os.path.join(out_dir, 'preview.png'))
    chrome = [chromium, '--headless=new', '--no-sandbox', '--hide-scrollbars', f'--window-size={size[0]},{size[1]}']
    try:
        # Headless Chrome's screenshot is the whole window, which is taller
        # than the page by a toolbar's height: find out by how much, to crop.
        r = subprocess.run(chrome + ['--dump-dom', 'data:text/html,<script>document.write(innerHeight)</script>'],
                           capture_output=True, text=True, timeout=60)
        m = re.search(r'<body>(\d+)', r.stdout)
        # Now and then Chrome takes the shot before three.js has arrived from
        # the CDN, leaving only the loading screen (a small, plain PNG): retry.
        for _ in range(3):
            subprocess.run(chrome + ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist',
                                     '--virtual-time-budget=30000', f'--screenshot={png}',
                                     f'http://127.0.0.1:{port}/index.html?still'],
                           check=True, timeout=180, capture_output=True)
            if os.path.getsize(png) > 300_000:
                break
        else:
            print('the preview only shows the loading screen', file=sys.stderr)
        if m:
            crop_png(png, int(m.group(1)))
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        print(f'no preview: {e}', file=sys.stderr)
    finally:
        srv.shutdown()


def crop_png(path, height):
    """Keep the top rows of an 8-bit PNG. Each row's filter refers only to
    the row above, so the rows can be cut without decoding them."""
    d = open(path, 'rb').read()
    i, chunks = 8, []
    while i < len(d):
        n = struct.unpack('>I', d[i:i + 4])[0]
        chunks.append((d[i + 4:i + 8], d[i + 8:i + 8 + n]))
        i += 12 + n
    ihdr = chunks[0][1]
    w, h, depth, colour = struct.unpack('>IIBB', ihdr[:10])
    if height >= h or depth != 8 or ihdr[12] != 0:
        return
    row = 1 + w * {0: 1, 2: 3, 4: 2, 6: 4}[colour]
    pixels = zlib.decompress(b''.join(c for t, c in chunks if t == b'IDAT'))[:row * height]

    def chunk(t, c):
        return struct.pack('>I', len(c)) + t + c + struct.pack('>I', zlib.crc32(t + c))
    out = d[:8] + chunk(b'IHDR', ihdr[:4] + struct.pack('>I', height) + ihdr[8:])
    out += b''.join(chunk(t, c) for t, c in chunks[1:] if t not in (b'IDAT', b'IEND'))
    out += chunk(b'IDAT', zlib.compress(pixels, 9)) + chunk(b'IEND', b'')
    open(path, 'wb').write(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', default='site/3d')
    args = ap.parse_args()
    build(args.out, os.environ.get('CHROMIUM'))


if __name__ == '__main__':
    main()
