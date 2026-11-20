"""Export everything garmin.vaw.be needs for the Garmin Wrapped page into a website-garmin checkout.

    python tools/export_site.py ../website-garmin [example_out_dir]

Writes:
  public/wrapped/                       static files an AI (or a person) can fetch
    garmin-wrapped-kit.zip              the kit (prompt, style guide, kit/)
    PROMPT.md SCHEMA.md STYLEGUIDE.md   raw text
    tokens.json compute.py wrapped.py   raw kit files
    manifest.json                       machine-readable index of all of the above
    avatar.jpg, img/…                   example slides, looping example clips, background strip
    scene/index.html + vendor/          the three.js + GSAP background scene, runnable in any browser
  src/app/[locale]/wrapped/content.ts   the markdown texts, embedded at build time (fully static page)
The page itself (page.tsx + wrapped.module.css) lives in the website repo.
"""
import json, os, shutil, subprocess, sys, zipfile
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, '..', 'website-garmin'))
EX = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'example', 'runner', 'out')
PUB = os.path.join(SITE, 'public', 'wrapped')
BASE = 'https://garmin.vaw.be/wrapped'
os.makedirs(os.path.join(PUB, 'img'), exist_ok=True)
os.makedirs(os.path.join(PUB, 'scene', 'vendor'), exist_ok=True)

# kit zip
zp = os.path.join(PUB, 'garmin-wrapped-kit.zip')
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in ('PROMPT.md', 'STYLEGUIDE.md', 'README.md'):
        z.write(os.path.join(ROOT, f), f)
    for dp, _, fs in os.walk(os.path.join(ROOT, 'kit')):
        for f in fs:
            if '__pycache__' in dp or f == '.DS_Store':
                continue
            full = os.path.join(dp, f)
            z.write(full, os.path.relpath(full, ROOT))

# raw text + kit files
for src, dst in [('PROMPT.md', 'PROMPT.md'), ('STYLEGUIDE.md', 'STYLEGUIDE.md'), ('kit/SCHEMA.md', 'SCHEMA.md'),
                 ('kit/style/tokens.json', 'tokens.json'), ('kit/compute.py', 'compute.py'), ('kit/wrapped.py', 'wrapped.py'),
                 ('kit/assets/avatar.jpg', 'avatar.jpg')]:
    shutil.copy(os.path.join(ROOT, src), os.path.join(PUB, dst))

# example visuals
slides = []
for i in range(1, 11):
    p = os.path.join(EX, f'garmin_wrapped_26_{i:02d}.png')
    if os.path.exists(p):
        Image.open(p).convert('RGB').resize((720, 900), Image.LANCZOS).save(os.path.join(PUB, 'img', f'slide_{i:02d}.jpg'), quality=86)
        slides.append(f'{BASE}/img/slide_{i:02d}.jpg')
clips = []
for k in (1, 3, 7):
    p = os.path.join(EX, f'garmin_wrapped_26_{k:02d}.mp4')
    if os.path.exists(p):
        shutil.copy(p, os.path.join(PUB, 'img', f'example_{k:02d}.mp4'))
        clips.append(f'{BASE}/img/example_{k:02d}.mp4')
bgs = [Image.open(os.path.join(ROOT, 'kit', 'assets', 'bg', f'bg_{i:02d}.jpg')).resize((216, 270), Image.LANCZOS) for i in range(1, 11)]
strip = Image.new('RGB', (2160, 270))
for i, im in enumerate(bgs):
    strip.paste(im, (i * 216, 0))
strip.save(os.path.join(PUB, 'img', 'backgrounds.jpg'), quality=86)

# three.js scene, standalone
scene = open(os.path.join(ROOT, 'scene', 'scene.html')).read()
scene = scene.replace('./node_modules/three/build/three.module.js', './vendor/three.module.js')
scene = scene.replace('./node_modules/gsap/dist/gsap.min.js', './vendor/gsap.min.js')
scene = scene.replace("await fetch('../kit/style/tokens.json')", "await fetch('../tokens.json')")
open(os.path.join(PUB, 'scene', 'index.html'), 'w').write(scene)
for src, dst in [('scene/node_modules/three/build/three.module.js', 'three.module.js'), ('scene/node_modules/gsap/dist/gsap.min.js', 'gsap.min.js')]:
    shutil.copy(os.path.join(ROOT, src), os.path.join(PUB, 'scene', 'vendor', dst))

tokens = json.load(open(os.path.join(ROOT, 'kit', 'style', 'tokens.json')))
manifest = {
    'name': "Garmin Wrapped '26 — by the Garmin School",
    'page': 'https://garmin.vaw.be/en/wrapped',
    'github': 'https://github.com/wimva/garmin-wrapped',
    'kit_zip': f'{BASE}/garmin-wrapped-kit.zip',
    'kit_zip_github': 'https://github.com/wimva/garmin-wrapped/archive/refs/heads/main.zip',
    'prompt': f'{BASE}/PROMPT.md', 'schema': f'{BASE}/SCHEMA.md', 'styleguide': f'{BASE}/STYLEGUIDE.md',
    'tokens': f'{BASE}/tokens.json', 'compute_py': f'{BASE}/compute.py', 'wrapped_py': f'{BASE}/wrapped.py',
    'avatar': f'{BASE}/avatar.jpg',
    'scene': {'url': f'{BASE}/scene/index.html', 'usage': 'Open ?slide=1..10 to play one slide window of the background strip; window.drawSlide(i0, t) renders slide i0 (0-based) at time t seconds; the loop is 6 s.'},
    'example_slides': slides, 'example_clips': clips, 'backgrounds_preview': f'{BASE}/img/backgrounds.jpg',
    'format': tokens['artboard'], 'type': tokens['type'], 'slides': tokens['slides'],
    'handles': {'instagram': '@vawbe', 'tiktok': '@vaw.be', 'youtube': '@vawbe', 'site': 'garmin.vaw.be'},
    'steps': ['Ask: stills or animated, first name, show real age, units', 'Download the kit zip',
              'Fetch Garmin data into data/*.json per SCHEMA.md', 'python kit/compute.py data',
              'python kit/wrapped.py data/wrapped.json --out out --stills|--video --sheet', 'Check contact_sheet.png, deliver files 01–10'],
}
json.dump(manifest, open(os.path.join(PUB, 'manifest.json'), 'w'), indent=1)

# embedded texts for the static page
def ts(s):
    return json.dumps(s, ensure_ascii=False)
prompt = open(os.path.join(ROOT, 'PROMPT.md')).read().split('\n---\n')[1].strip()
content = ('// Generated by garmin-wrapped/tools/export_site.py — do not edit by hand.\n'
           f'export const PROMPT = {ts(prompt)};\n'
           f'export const SCHEMA = {ts(open(os.path.join(ROOT, "kit", "SCHEMA.md")).read())};\n'
           f'export const STYLEGUIDE = {ts(open(os.path.join(ROOT, "STYLEGUIDE.md")).read())};\n'
           f'export const TOKENS = {json.dumps(tokens)} as const;\n'
           f'export const SLIDES = {json.dumps(slides)};\n'
           f'export const CLIPS = {json.dumps(clips)};\n')
page_dir = os.path.join(SITE, 'src', 'app', '[locale]', 'wrapped')
os.makedirs(page_dir, exist_ok=True)
open(os.path.join(page_dir, 'content.ts'), 'w').write(content)
total = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(PUB) for f in fs)
print(f'public/wrapped: {total / 1e6:.1f} MB, {len(slides)} slides, {len(clips)} clips; content.ts written')
