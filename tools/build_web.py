"""Build web/index.html (the garmin.vaw.be/wrapped page) from PROMPT.md and the example slides.
    python tools/build_web.py [example_out_dir]
"""
import html, os, shutil, sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, 'web')
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'example', 'runner', 'out')
os.makedirs(os.path.join(WEB, 'img'), exist_ok=True)
os.makedirs(os.path.join(WEB, 'fonts'), exist_ok=True)
for f in ('BebasNeue-Regular.ttf', 'Geist-VariableFont_wght.ttf'):
    shutil.copy(os.path.join(ROOT, 'kit', 'assets', 'fonts', f), os.path.join(WEB, 'fonts', f))
imgs = []
for i in range(1, 11):
    p = os.path.join(src, f'garmin_wrapped_26_{i:02d}.png')
    if os.path.exists(p):
        Image.open(p).convert('RGB').resize((720, 900), Image.LANCZOS).save(os.path.join(WEB, 'img', f'slide_{i:02d}.jpg'), quality=86)
        imgs.append(f'img/slide_{i:02d}.jpg')
for k in (1, 3, 7):
    v = os.path.join(src, f'garmin_wrapped_26_{k:02d}.mp4')
    if os.path.exists(v):
        shutil.copy(v, os.path.join(WEB, 'img', f'example_{k:02d}.mp4'))
if os.path.exists(os.path.join(WEB, 'img', 'example_all.mp4')):
    os.remove(os.path.join(WEB, 'img', 'example_all.mp4'))

vids = [f'img/example_{k:02d}.mp4' for k in (1, 3, 7) if os.path.exists(os.path.join(WEB, 'img', f'example_{k:02d}.mp4'))]
video = ('<section><div class="wrap"><h2>Or animated</h2><p>Every slide is its own looping video.</p><div style="display:flex;gap:12px;flex-wrap:wrap">'
         + ''.join(f'<video src="{v}" autoplay muted playsinline loop style="width:min(100%,320px);border-radius:14px"></video>' for v in vids)
         + '</div></div></section>') if vids else ''
prompt = open(os.path.join(ROOT, 'PROMPT.md')).read().split('\n---\n')[1].strip()
cards = '\n'.join(f'<img src="{p}" alt="Example slide {k + 1}" loading="lazy">' for k, p in enumerate(imgs))
page = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Garmin Wrapped '26 — free prompt by the Garmin School</title>
<meta name="description" content="Turn your Garmin data into a Spotify Wrapped-style carousel with Claude or ChatGPT. Free prompt from the Garmin School.">
<meta property="og:image" content="img/slide_01.jpg">
<style>
@font-face {{ font-family: Bebas; src: url(fonts/BebasNeue-Regular.ttf); }}
@font-face {{ font-family: Geist; src: url(fonts/Geist-VariableFont_wght.ttf); font-weight: 100 900; }}
:root {{ --v: #4B1FD1; --p: #FF2E88; --o: #FF6B1A; --y: #FFD23F; --l: #C6F432; --n: #13101F; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font: 400 19px/1.55 Geist, system-ui, sans-serif; color: #fff; background: var(--n); }}
a {{ color: var(--l); }}
.hero {{ padding: 64px 24px 40px; background: linear-gradient(100deg, var(--v), var(--p) 45%, var(--o) 75%, var(--y)); }}
.wrap {{ max-width: 1080px; margin: 0 auto; }}
.pill {{ display: inline-block; background: #fff; color: var(--v); font: 600 15px/1 Geist; letter-spacing: 1.5px; padding: 10px 18px; border-radius: 99px; }}
h1 {{ font: 400 clamp(72px, 14vw, 168px)/.86 Bebas; margin: 22px 0 8px; text-transform: uppercase; }}
h1 span {{ color: var(--l); }}
h2 {{ font: 400 56px/1 Bebas; margin: 0 0 18px; text-transform: uppercase; }}
.lead {{ font-size: 22px; max-width: 640px; }}
.btns {{ display: flex; gap: 12px; flex-wrap: wrap; margin-top: 26px; }}
.btn {{ font: 600 17px/1 Geist; padding: 16px 24px; border-radius: 99px; border: 0; cursor: pointer; text-decoration: none; }}
.btn.main {{ background: var(--n); color: #fff; }}
.btn.alt {{ background: #fff; color: var(--n); }}
.strip {{ display: flex; gap: 12px; overflow-x: auto; padding: 28px 24px; scroll-snap-type: x mandatory; }}
.strip img {{ height: min(62vh, 560px); aspect-ratio: 4/5; border-radius: 14px; scroll-snap-align: start; }}
section {{ padding: 56px 24px; }}
.steps {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 18px; }}
.step {{ background: #221c38; border-radius: 18px; padding: 22px; }}
.step b {{ font: 400 48px/1 Bebas; color: var(--l); display: block; }}
pre {{ white-space: pre-wrap; background: #221c38; border-radius: 18px; padding: 24px; font: 400 15px/1.55 ui-monospace, Menlo, monospace; max-height: 520px; overflow: auto; }}
footer {{ padding: 40px 24px 64px; color: #bdb6d6; font-size: 16px; }}
</style>
</head>
<body>
<div class="hero"><div class="wrap">
  <span class="pill">BY THE GARMIN SCHOOL</span>
  <h1>Garmin<br><span>Wrapped '26</span></h1>
  <p class="lead">Your year on the wrist as a Spotify Wrapped-style carousel. Paste one prompt into Claude or ChatGPT,
  and your assistant turns your own Garmin data into 10 slides — stills or animated — for Instagram and TikTok. Free.</p>
  <div class="btns">
    <button class="btn main" id="copy">Copy the prompt</button>
    <a class="btn alt" href="garmin-wrapped-kit.zip">Download the kit</a>
    <a class="btn alt" href="https://github.com/wimva/garmin-wrapped">GitHub</a>
  </div>
</div></div>
<div class="strip">{cards}</div>
{video}
<section><div class="wrap">
  <h2>How it works</h2>
  <div class="steps">
    <div class="step"><b>1</b>Connect your Garmin to Claude or ChatGPT. <a href="https://garmin.vaw.be/en/community/extra-garmin-personal-api-claude-extension">Here's how</a>.</div>
    <div class="step"><b>2</b>Turn on code execution, paste the prompt and answer four quick questions.</div>
    <div class="step"><b>3</b>Get 10 PNGs or MP4s and post them as one carousel. Tag @vawbe!</div>
  </div>
</div></section>
<section><div class="wrap">
  <h2>The prompt</h2>
  <pre id="prompt">{html.escape(prompt)}</pre>
</div></section>
<footer><div class="wrap">
  Made by Wim from the <a href="https://garmin.vaw.be">Garmin School</a> · Instagram <a href="https://instagram.com/vawbe">@vawbe</a> ·
  TikTok <a href="https://tiktok.com/@vaw.be">@vaw.be</a> · YouTube <a href="https://www.youtube.com/@vawbe">@vawbe</a><br>
  Not affiliated with Garmin. Example slides use fake data. Everything runs inside your own assistant.
</div></footer>
<script>
document.getElementById('copy').onclick = async (e) => {{
  await navigator.clipboard.writeText(document.getElementById('prompt').innerText);
  e.target.textContent = 'Copied';
  setTimeout(() => e.target.textContent = 'Copy the prompt', 1800);
}};
</script>
</body>
</html>
'''
open(os.path.join(WEB, 'index.html'), 'w').write(page)
print('web/index.html with', len(imgs), 'slides')
