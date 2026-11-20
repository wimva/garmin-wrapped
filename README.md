# Garmin Wrapped '26 — by the Garmin School

Your Garmin year as a Spotify Wrapped-style carousel for Instagram and TikTok: ten slides, stills or
animated (every slide its own seamless loop), made by your own AI assistant (Claude or ChatGPT) from your own Garmin data.

**Use it:** copy [`PROMPT.md`](PROMPT.md) (also on [garmin.vaw.be/en/wrapped](https://garmin.vaw.be/en/wrapped)) into Claude or ChatGPT with a Garmin connector switched on.
That's all. The assistant downloads this kit, fetches your data, picks the slides that fit *your* year
(running, cycling, rowing, strength, padel…) and hands you the PNGs or MP4s.

Made by Wim from the [Garmin School](https://garmin.vaw.be) — Instagram [@vawbe](https://instagram.com/vawbe) ·
TikTok [@vaw.be](https://tiktok.com/@vaw.be) · YouTube [@vawbe](https://www.youtube.com/@vawbe).
Not affiliated with Garmin. No Garmin logos are used.

## How it works

```
Garmin connector (MCP)  →  data/*.json  →  kit/compute.py  →  wrapped.json  →  kit/wrapped.py  →  PNG / MP4
        the assistant        normalized       picks 8 slides     editable plan     draws the slides
```

1. **Data:** the assistant writes a few small JSON files (format: [`kit/SCHEMA.md`](kit/SCHEMA.md)).
2. **Plan:** `python kit/compute.py data` computes the stats and chooses the 8 strongest middle slides from
   the module library, with the athlete's main sports first. It needs only the Python standard library.
3. **Render:** `python kit/wrapped.py data/wrapped.json --out out --stills` (or `--video`) draws the data
   layer on top of pre-rendered three.js backgrounds. It needs Pillow, plus ffmpeg (or `imageio-ffmpeg`,
   or OpenCV) for video.

Design rules: [`STYLEGUIDE.md`](STYLEGUIDE.md).

## Try it without a Garmin account

```bash
pip install pillow imageio-ffmpeg
python tools/make_example.py runner        # or cyclist / lifter — fake data
python kit/compute.py example/runner
python kit/wrapped.py example/runner/wrapped.json --out out --stills --sheet
python kit/wrapped.py example/runner/wrapped.json --out out --video
```

## Repo

| path | what |
|---|---|
| `PROMPT.md` | the prompt people paste into Claude/ChatGPT |
| `STYLEGUIDE.md` | the "Prism" design language |
| `kit/compute.py` | stats, sport detection, slide selection, privacy trimming |
| `kit/wrapped.py` | renderer (stills + animation), module layouts |
| `kit/style/tokens.json` | colours, type sizes, layout values (shared by the scene and the renderer) |
| `kit/assets/bg/` | pre-rendered backgrounds: `bg_NN.jpg` (2160×2700) and `bg_NN.mp4` (6 s seamless loops) |
| `kit/assets/fonts/` | Bebas Neue and Geist (SIL Open Font License) |
| `kit/assets/avatar.jpg` | Wim's avatar for the call-to-action slide |
| `scene/` | the three.js + GSAP source of the backgrounds and `render_bg.py` to re-render them |
| `tools/` | example data generator, `export_site.py` (publishes everything to garmin.vaw.be) |
| `example/` | fake datasets (runner, cyclist, lifter) and their rendered slides |

## Changing the look

Edit `kit/style/tokens.json` (colours, sizes) and/or `scene/scene.html` (3D composition), then:

```bash
cd scene && npm install && cd ..
python scene/render_bg.py --stills     # 10 × JPG
python scene/render_bg.py --loops      # 10 × MP4 (about a minute per slide with software WebGL)
python tools/export_site.py ../website-garmin   # kit zip, raw files, examples, scene → garmin.vaw.be/wrapped
```

## Privacy

The kit never draws maps, addresses or coordinates. Routes are shown as a line only, with the first and last
200 m removed. Weight, BMI, body composition, menstrual and food data are never requested or shown. Everything
runs inside the user's own assistant; nothing is sent to the Garmin School.
