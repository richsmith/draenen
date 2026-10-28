# draenen

The survey of Ogof Draenen in [Therion](https://therion.speleo.sk/): the
Grade 2 survey data from Oxford University Cave Club, converted to
Therion, and newer surveys with their drawings.

GitHub Actions builds it on every push, and on `main` publishes the
outputs to the [latest release](https://github.com/richsmith/draenen/releases/tag/latest)
and the site to GitHub Pages:

| Output | What it is |
|---|---|
| `draenen-plan.pdf` | The plan at 1:5000, coloured by altitude: the centreline, the drawings, the passage names and the entrances, with the length, depth, credits and a key to the colours in the header. |
| `draenen.3d` | The survey as a Survex 3D file, for Aven. |
| The site | The cave in 3D beneath the Welsh Government's LiDAR ground, with a route planner: turn-by-turn routes between any two places, that work offline underground and in AR. |

## Building

```bash
cd survey && therion draenen.thconfig    # draenen-plan.pdf and draenen.3d
cd .. && python3 -m tools.site           # the site, in site/
python3 -m http.server -d site           # then open http://localhost:8000
```

The tools need only Python 3. Set `CHROMIUM` to a Chrome binary for the
site's preview image.

## Names and entrances

`survey/names.json` names the passages (by survey file), the junctions
and the entrances, for the plan, the 3D view and the routes. The
entrances are flagged in the survey (`station … entrance`).

## The plan's colour and names

The plan is coloured by altitude. Therion colours scraps, not survey
lines, so `survey/plan.th` has the centreline in short pieces, each a
scrap with the piece as a line `u:ribbon`, which the layout
(`draenen.thconfig`) draws as a band 1.4 mm wide with round ends in the
scrap's colour: by altitude, the highest on top. It also has the passage names, each at the
station nearest the middle of its passage, and the entrances. Surveys
with drawings of their own get no ribbon.

`plan.th` is made from the built survey (and Therion's database of it,
`draenen-stations.sql`), so after changing the names or the surveys,
make it again and rebuild (CI does this on every build):

```bash
python3 -m tools.plan && (cd survey && therion draenen.thconfig)
```

Tarddiad Pwll Du's tie into the cave is provisional (see
`survey/north/north.th`), so the 3D view shows its entrance but leaves
it out of the routes until the tie is known.

## On the grid

The entrance is fixed where OUCC fixed the same station (SO 24650 11750,
380 m), so heights are above sea level and the survey lines up with the
LiDAR and imagery in the 3D view. It's fixed without a coordinate system
(`cs`): with one, Therion would also turn the survey for magnetic
declination, and the Grade 2 data's `calibrate compass` corrections
already take it to grid north.

## Tools

| | |
|---|---|
| `tools/names.py` | The names and the move onto the grid, for the other tools. |
| `tools/plan.py` | Writes `survey/plan.th`: the plan's coloured ribbon, names and entrances. |
| `tools/model3d/` | The 3D view and route planner; `lidar/` keeps the LiDAR it's built on. |
| `tools/site/` | The site: a landing page, the 3D view and the outputs. |

The tools are GPL-3.0 (`tools/LICENSE`); the 3D view started as the one
made for the [Swildons Hole survey](https://github.com/CaveSurveying/uk_mendips_swildons-hole).
The ground is Welsh Government LiDAR 2020–22, © Welsh Government,
[Open Government Licence v3](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
