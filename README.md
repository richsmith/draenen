# draenen

The survey of Ogof Draenen in [Therion](https://therion.speleo.sk/): the
Grade 2 survey data from Oxford University Cave Club, converted to
Therion, and newer surveys with their drawings.

GitHub Actions builds it on every push, and on `main` publishes the
outputs to the [latest release](https://github.com/richsmith/draenen/releases/tag/latest)
and the site to GitHub Pages:

| Output | What it is |
|---|---|
| `draenen-plan.pdf` | The plan at 1:5000: the centreline, the drawings, the passage names and the entrances, with the length, depth and credits in the header. |
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

The names on the plan are scraps of their own in `survey/names.th`, each
at the station nearest the middle of its passage. It's made from the
built survey, so after changing the names or the surveys, make it again
and rebuild (CI does this on every build):

```bash
python3 -m tools.plannames && (cd survey && therion draenen.thconfig)
```

Tarddiad Pwll Du's tie into the cave is provisional (see
`survey/north/north.th`), so the 3D view shows its entrance but leaves
it out of the routes until the tie is known.

## On the grid

The survey is in its own coordinates, with the entrance at 0 0 0. The 3D
view moves it onto the National Grid at OUCC's fixed point for the same
station (SO 24650 11750, 380 m), without changing its shape, to line it
up with the LiDAR and imagery.

## Tools

| | |
|---|---|
| `tools/names.py` | The names and the move onto the grid, for the other tools. |
| `tools/plannames.py` | Writes `survey/names.th`, the names for the plan. |
| `tools/model3d/` | The 3D view and route planner; `lidar/` keeps the LiDAR it's built on. |
| `tools/site/` | The site: a landing page, the 3D view and the outputs. |

The tools are GPL-3.0 (`tools/LICENSE`); the 3D view started as the one
made for the [Swildons Hole survey](https://github.com/CaveSurveying/uk_mendips_swildons-hole).
The ground is Welsh Government LiDAR 2020–22, © Welsh Government,
[Open Government Licence v3](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
