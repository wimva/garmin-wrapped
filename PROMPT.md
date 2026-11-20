# Garmin Wrapped '26 — the prompt

Copy everything between the lines into Claude or ChatGPT (desktop or mobile), with your Garmin connector
switched on and code execution (file creation) enabled.

---

Make my **Garmin Wrapped '26**: a 10-slide Instagram/TikTok carousel of my Garmin data from 1 January 2026
until today, in the style of Spotify Wrapped. Use the Garmin School kit so it looks exactly right.

**Step 0 — Ask me first, in one short message, then wait for my answer:**
1. Stills (10 PNG images) or animated (10 short MP4 videos with a moving background that loop seamlessly,
   plus the same 10 slides as PNGs as a backup)?
2. Which first name should be on slide 1? (Or none.)
3. Can the fitness age slide show my real age next to my fitness age? (yes/no)
4. Metric or imperial?

**Step 1 — Get the kit.** In your code environment, download and unzip
`https://github.com/wimva/garmin-wrapped/archive/refs/heads/main.zip`
(mirror: `https://garmin.vaw.be/wrapped/garmin-wrapped-kit.zip`). If downloading is blocked, ask me to download
that zip and upload it here, then continue. Read `kit/SCHEMA.md` before fetching anything. Everything about
this kit (steps, data format, style guide, example slides, the three.js scene) is also on
`https://garmin.vaw.be/en/wrapped` and in `https://garmin.vaw.be/wrapped/manifest.json`: read those if anything is unclear.
Install what is missing: `pip install pillow imageio-ffmpeg`. Then run `python kit/wrapped.py --check`.
If I chose animated and it says `VIDEO: NOT POSSIBLE`, fix that now exactly as it says (it may mean uploading one
file); don't continue until `--check` says `VIDEO: OK`.

**Step 2 — Fetch my data with my Garmin tools** (Jan 1 → today). Follow `kit/SCHEMA.md`:
- all activities (page through the activity list, 100 at a time, until you pass 1 January)
- daily summaries (steps, floors, resting heart rate, intensity minutes, active calories)
- sleep for every night (sleep tools usually give 31 nights per call)
- VO2 max history, HRV history, fitness age
After each tool call, immediately write **only the fields in SCHEMA.md** into the `data/` files with code.
Never paste raw tool output into a file or into the chat, and never invent or estimate a number: if a tool
fails or data is missing, leave that part out.

**Step 3 — Plan the slides:** run `python kit/compute.py data`. It picks the 8 strongest middle slides for
*my* year (a cyclist gets cycling slides, a rower gets rowing, a lifter gets strength). If it prints
`routes_to_fetch`, get the GPS polyline of one of those activities, save it to `data/routes/<id>.json`
as `[[lat, lon], ...]` and run `compute.py` again. Show me the 10-slide list. You may reword a
headline or body in `data/wrapped.json` to make it sound more like me, but keep every number as computed.

**Step 4 — Render with the kit's code** (never write your own renderer, never draw slides another way):
- stills: `python kit/wrapped.py data/wrapped.json --out out --stills --sheet` → 10 PNGs
- animated: `python kit/wrapped.py data/wrapped.json --out out --video --sheet` → 10 MP4s + the same 10 PNGs
  (`garmin_wrapped_26_01.mp4` … `_10.mp4`, 6 s each; the data stays still and the 3D background moves in a
  seamless loop). It takes about 2 seconds per slide; if your environment still times out, run
  `--slides 1 2 3`, then `4 5 6`, then `7 8 9 10`.

If I asked for animated, you must deliver the MP4 files (with the PNGs as a backup), never only PNGs. If a step fails, show me the error and fix it.
Open `out/contact_sheet.png` and check every slide: no text cut off or overlapping, numbers match my data.
Fix and re-render any slide that's wrong.

**Step 5 — Deliver:** list the `out/` folder first to confirm the files exist. Then give me a download link
for every file, in order 01 → 10 (animated: the 10 MP4s and the 10 PNGs; stills: the 10 PNGs), plus one zip
with all of them. Then **always** finish with my two captions from `out/captions.txt` (the kit writes them
with my real numbers): the **Instagram caption** and the **TikTok caption**, each in its own copyable block. You may
make them sound more like me, but keep the numbers, the credit line (Instagram @vawbe, TikTok @vaw.be) and the
hashtags. Don't use official Garmin logos anywhere.

**Privacy (always):** no weight, BMI, body composition, menstrual or food data, no addresses, no maps. The
route slide shows only the shape of the line, with the first and last 200 m removed.

---

*Made by Wim from the Garmin School — Instagram @vawbe · TikTok @vaw.be · YouTube @vawbe · garmin.vaw.be*
