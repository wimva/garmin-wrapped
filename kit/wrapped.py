#!/usr/bin/env python3
"""Garmin Wrapped '26 — step 3: render wrapped.json into carousel slides (PNG stills and/or MP4 videos).

    python wrapped.py DATA_DIR/wrapped.json --out OUT_DIR --stills            # 10 PNGs, 2160x2700 (4:5)
    python wrapped.py DATA_DIR/wrapped.json --out OUT_DIR --video --sheet     # 10 MP4s (1080x1350, 6 s seamless loops) + the 10 PNGs
    python wrapped.py --check                   # fonts, backgrounds and video support (run this first)
    python wrapped.py ... --slides 3 4          # only some slides (handy in sandboxes with short time limits)
    python wrapped.py ... --sheet               # also writes contact_sheet.png to check the whole strip at once

Needs Pillow. Video needs ffmpeg (system ffmpeg, or `pip install imageio-ffmpeg`) or OpenCV + numpy.
The three.js/GSAP background art is pre-rendered in assets/bg (stills + 6 s seamless loops). This script draws the
static data layer on top. In a video only the background moves, so every MP4 loops seamlessly on its own,
and one ffmpeg call per slide makes it fast (about a second per slide).
"""
import argparse, datetime as dt, json, math, os, shutil, subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
TOK = json.load(open(os.path.join(HERE, 'style', 'tokens.json')))
W, H = TOK['artboard']['width'], TOK['artboard']['height']
S = TOK['artboard']['png_scale']                 # drawing scale: everything is drawn at 2160x2700
FPS, SECONDS = TOK['artboard']['video_fps'], TOK['artboard']['video_seconds']
MX = TOK['layout']['margin_x']
TYPE = TOK['type']
MIN_PX = TYPE['minimum']                          # Garmin School rule: never smaller than this
FONT_DIR = os.path.join(HERE, 'assets', 'fonts')
BG_DIR = os.path.join(HERE, 'assets', 'bg')


# ============================================================================================ helpers
def hexrgb(h, a=255):
    h = h.lstrip('#')
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(a))


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(t, t0, dur=0.55):
    x = clamp((t - t0) / dur)
    return 1 - (1 - x) ** 3


def ease_expo(t, t0, dur):
    x = clamp((t - t0) / dur)
    return 1 if x >= 1 else 1 - 2 ** (-10 * x)


_fonts = {}


def font(kind, size, weight=400):
    size = max(size, MIN_PX)
    key = (kind, size, weight)
    if key not in _fonts:
        f = ImageFont.truetype(os.path.join(FONT_DIR, TOK['fonts']['display' if kind == 'display' else 'body']), int(round(size * S)))
        if kind != 'display':
            try:
                f.set_variation_by_axes([weight])
            except Exception:
                pass
        _fonts[key] = f
    return _fonts[key]


def tw(s, f):
    b = f.getbbox(s)
    return (b[2] - b[0]) / S


def fit(s, kind, size, max_w, min_size=None, weight=400):
    """Largest size <= size that fits max_w (base px). Never below the minimum type size."""
    min_size = max(min_size or MIN_PX, MIN_PX)
    while size > min_size and tw(s, font(kind, size, weight)) > max_w:
        size -= 2
    return size


def base_off(f):
    """Distance (base px) from a 'la'-anchored y to the baseline."""
    return f.getbbox('H', anchor='la')[3] / S


def cap_top(f):
    return f.getbbox('H', anchor='la')[1] / S


def wrap(s, f, max_w):
    words, lines, cur = s.split(), [], ''
    for w_ in words:
        t = (cur + ' ' + w_).strip()
        if tw(t, f) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines


def fmt_number(n, t):
    v = n['value'] * t
    dec = n.get('decimals', 0)
    s = f'{v:,.{dec}f}' if dec else f'{int(round(v)):,}'
    return f"{n.get('prefix', '')}{s}{n.get('suffix', '')}"


def tri_pts(cx, cy, r, rot=0.0):
    return [((cx + r * math.cos(rot - math.pi / 2 + k * 2 * math.pi / 3)) * S, (cy + r * math.sin(rot - math.pi / 2 + k * 2 * math.pi / 3)) * S) for k in range(3)]


# ============================================================================================ canvas
class Slide:
    def __init__(self, idx, data, total=10):
        self.i, self.d, self.n = idx, data, total
        p = TOK['slides'][idx]
        self.bg, self.ink, self.acc, self.shape, self.shape2 = (hexrgb(p['bg']), hexrgb(p['ink']), hexrgb(p['accent']),
                                                                hexrgb(p['shape']), hexrgb(p['shape2']))
        self.img = None

    def inkA(self, a):
        return self.ink[:3] + (int(255 * a),)

    # every element is drawn through put(). The data layer is static (Wim, 2026-11-20): in the animated
    # version only the three.js background moves, so put() draws immediately and ignores the timing args.
    def put(self, t, t0, fn, dur=0.55, rise=40):
        fn(ImageDraw.Draw(self.img))

    def text(self, dr, xy, s, f, fill, anchor='la', tracking=0):
        x, y = xy
        if not tracking:
            dr.text((x * S, y * S), s, font=f, fill=fill, anchor=anchor)
            return
        total = sum(tw(c, f) for c in s) + tracking * (len(s) - 1)
        if anchor[0] == 'm':
            x -= total / 2
        elif anchor[0] == 'r':
            x -= total
        for c in s:
            dr.text((x * S, y * S), c, font=f, fill=fill, anchor='l' + anchor[1])
            x += tw(c, f) + tracking

    def tri(self, dr, cx, cy, r, fill=None, outline=None, width=0, rot=0.0):
        pts = tri_pts(cx, cy, r, rot)
        if fill:
            dr.polygon(pts, fill=fill)
        if outline:
            dr.line(pts + [pts[0], pts[1]], fill=outline, width=int(width * S), joint='curve')

    def rrect(self, dr, box, r, fill=None, outline=None, width=0):
        dr.rounded_rectangle([v * S for v in box], radius=r * S, fill=fill, outline=outline, width=int(width * S))

    # ---------------------------------------------------------------- chrome (every slide)
    def chrome(self, dr):
        f = font('body', TYPE['tag'], 600)
        label = 'BY THE GARMIN SCHOOL'
        w = sum(tw(c, f) for c in label) + 1.6 * (len(label) - 1)
        x0, y0, h = MX, TOK['layout']['tag_top'] - 2, 64
        self.rrect(dr, (x0, y0, x0 + w + 56, y0 + h), h / 2, fill=self.ink)
        self.text(dr, (x0 + 28, y0 + h / 2 + 1), label, f, self.bg, 'lm', tracking=1.6)
        # progress: ten small triangles, current one filled
        for k in range(self.n):
            cx = W - MX - (self.n - 1 - k) * 27
            if k == self.i:
                self.tri(dr, cx, y0 + h / 2 + 2, 11, fill=self.ink)
            else:
                self.tri(dr, cx, y0 + h / 2 + 2, 9, outline=self.inkA(0.55), width=2.2)

    def kicker(self, dr, s, y=178):
        f = font('body', TYPE['kicker'], 600)
        s = s.upper()
        while sum(tw(c, f) for c in s) + 2 * len(s) > W - 2 * MX and len(s) > 4:
            s = s[:-2].rstrip() + '…'
        self.text(dr, (MX, y), s, f, self.inkA(0.88), 'la', tracking=2)

    def headline(self, dr, s, y=226, size=None, color=None, max_w=None):
        size = fit(s.upper(), 'display', size or 112, max_w or W - 2 * MX, 84)
        self.text(dr, (MX, y), s.upper(), font('display', size), color or self.ink)
        return y + size * 0.9

    def body(self, dr, s, y, size=None, color=None, max_w=None, anchor='la', x=None):
        f = font('body', size or TYPE['body'], 400)
        lines = wrap(s, f, max_w or W - 2 * MX)
        lh = (size or TYPE['body']) * 1.22   # Garmin School carousel body: Geist 42 / 1.22
        for k, ln in enumerate(lines):
            self.text(dr, ((x if x is not None else (W / 2 if anchor[0] == 'm' else MX)), y + k * lh), ln, f, color or self.ink, anchor)
        return y + len(lines) * lh

    def stats_row(self, dr, stats, y):
        n = len(stats)
        colw = (W - 2 * MX) / n
        for k, (val, lab) in enumerate(stats):
            x = MX + k * colw
            vs = fit(str(val), 'display', 88, colw - 24, 56)
            self.text(dr, (x, y), str(val), font('display', vs), self.ink)
            fl = font('body', 34, 500)
            lab_lines = wrap(lab, fl, colw - 20)[:2]
            for j, ln in enumerate(lab_lines):
                self.text(dr, (x, y + 92 + j * 40), ln, fl, self.inkA(0.85))
            if k:
                dr.line([(x - 16) * S, (y + 8) * S, (x - 16) * S, (y + 150) * S], fill=self.inkA(0.35), width=int(2 * S))

    # ---------------------------------------------------------------- render
    def render(self, t):
        self.img = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0))
        dr = ImageDraw.Draw(self.img)
        self.chrome(dr)
        getattr(self, 'm_' + self.d['module'])(t, self.d)
        return self.img

    # ================================================================ modules
    def m_intro(self, t, d):
        self.put(t, 0.1, lambda dr: self.kicker(dr, d['kicker'], 214))
        l1, l2 = [s.upper() for s in d['title']]
        size = min(fit(l1, 'display', 230, 900), fit(l2, 'display', 230, 900))
        self.put(t, 0.25, lambda dr: self.text(dr, (MX - 4, 262), l1, font('display', size), self.ink), rise=60)
        self.put(t, 0.42, lambda dr: self.text(dr, (MX - 4, 262 + size * 0.86), l2, font('display', size), self.acc), rise=60)
        hy = 262 + size * 1.86 + 40
        n = d['hook']['number']
        ns = fmt_number(n, ease_expo(t, 0.7, 1.6))
        self.put(t, 0.7, lambda dr: self.text(dr, (MX - 2, hy), ns, font('display', 210), self.ink))
        self.put(t, 0.9, lambda dr: self.text(dr, (MX, hy + 196), d['hook']['unit'].upper(), font('display', fit(d['hook']['unit'].upper(), 'display', 84, 900)), self.ink))

        def footer(dr):
            fs = 46
            f = font('body', fs, 500)
            l1_, l2_ = d['footer']
            y1 = 1190
            self.text(dr, (W / 2, y1), l1_, f, self.ink, 'ms')
            # arrow after line 1, on the middle of the x-height (Garmin School carousel rule), scaled with the text
            x = W / 2 + tw(l1_, f) / 2 + 28
            ym = y1 - fs * 0.26
            dr.line([x * S, ym * S, (x + 110) * S, ym * S], fill=self.ink, width=int(3.2 * S))
            dr.polygon([((x + 126) * S, ym * S), ((x + 108) * S, (ym - 8) * S), ((x + 108) * S, (ym + 8) * S)], fill=self.ink)
            self.text(dr, (W / 2, y1 + 54), l2_, font('body', 38, 400), self.inkA(0.88), 'ms')
        self.put(t, 1.3, footer, rise=20)

    def m_big_number(self, t, d):
        self.put(t, 0.1, lambda dr: self.kicker(dr, d['kicker']))
        yh = 226
        self.put(t, 0.22, lambda dr: self.headline(dr, d['headline'], yh))
        n = d['number']
        final = fmt_number(n, 1)
        size = fit(final, 'display', TYPE['hero_number'], W - 2 * MX, 180)
        ny = 336
        cur = fmt_number(n, ease_expo(t, 0.45, 1.7))
        fn = font('display', size)
        self.put(t, 0.42, lambda dr: self.text(dr, (MX - 6, ny), cur, fn, self.acc), rise=50)
        nb = ny + base_off(fn) + (size * 0.09 if ',' in final or '.' in final else 0)
        unit = d.get('unit', '').upper()
        fu = font('display', fit(unit, 'display', 104, 900))
        uy = nb + 30 - cap_top(fu)
        self.put(t, 0.62, lambda dr: self.text(dr, (MX, uy), unit, fu, self.ink))
        by = uy + base_off(fu) + 44
        if d.get('body'):
            end = [by]
            self.put(t, 0.95, lambda dr: end.__setitem__(0, self.body(dr, d['body'], by)))
            by = by + TYPE['body'] * 1.22 * len(wrap(d['body'], font('body', TYPE['body']), W - 2 * MX)) + 22
        stats = d.get('stats') or []
        if stats:
            sy = min(max(by + 18, 975), 990)
            self.put(t, 1.15, lambda dr: self.stats_row(dr, stats, sy))
        elif d.get('tri_count'):
            k = int(d['tri_count'])
            per = 20
            for j in range(k):
                row, col = divmod(j, per)
                cx = MX + 22 + col * 46
                cy = max(by + 40, 990) + row * 54
                if cy > 1120:
                    break
                self.put(t, 1.0 + j * 0.03, lambda dr, cx=cx, cy=cy: self.tri(dr, cx, cy, 18, fill=self.ink), dur=0.3, rise=14)

    def m_podium(self, t, d):
        self.put(t, 0.1, lambda dr: self.kicker(dr, d['kicker']))
        self.put(t, 0.22, lambda dr: self.headline(dr, d['headline'], 226))
        items = d['items'][:3]
        mx_h = max(i['hours'] for i in items) or 1
        order = [1, 0, 2] if len(items) == 3 else [0, 1]
        xs = {3: [235, 540, 845], 2: [320, 760]}[len(items)]
        base = 950
        cols = [self.acc, self.ink, self.inkA(0.6)]
        for slot, k in enumerate(order):
            it = items[k]
            r = 120 + 140 * math.sqrt(it['hours'] / mx_h)
            g = ease(t, 0.5 + 0.18 * slot, 0.8)
            cx = xs[slot]
            rr = r * (0.25 + 0.75 * g)
            cy = base - rr * 0.5          # equilateral: bottom edge sits at cy + r/2
            def draw(dr, cx=cx, cy=cy, rr=rr, k=k, it=it):
                self.tri(dr, cx, cy, rr, fill=cols[k])
                self.text(dr, (cx, cy + rr * 0.22), str(k + 1), font('display', max(MIN_PX, int(rr * 0.62))), self.bg, 'mm')
            self.put(t, 0.5 + 0.18 * slot, draw, rise=0)
            def lab(dr, cx=cx, it=it):
                ns = fit(it['name'].upper(), 'display', 62, 300, 40)
                self.text(dr, (cx, base + 30), it['name'].upper(), font('display', ns), self.ink, 'mt')
                self.text(dr, (cx, base + 98), f"{it['hours']:,.0f} h · {it['sessions']}×", font('body', 38, 500), self.inkA(0.88), 'mt')
            self.put(t, 1.0 + 0.15 * slot, lab)

    def m_route(self, t, d):
        self.put(t, 0.1, lambda dr: self.kicker(dr, d['kicker']))
        self.put(t, 0.22, lambda dr: self.headline(dr, d['headline'], 226))
        pts = d['points']
        lat0 = sum(p[0] for p in pts) / len(pts)
        xy = [(p[1] * math.cos(math.radians(lat0)), -p[0]) for p in pts]
        x0, x1 = min(p[0] for p in xy), max(p[0] for p in xy)
        y0, y1 = min(p[1] for p in xy), max(p[1] for p in xy)
        box = (110, 370, 970, 960)
        sc = min((box[2] - box[0]) / max(1e-9, x1 - x0), (box[3] - box[1]) / max(1e-9, y1 - y0))
        ox = box[0] + ((box[2] - box[0]) - (x1 - x0) * sc) / 2
        oy = box[1] + ((box[3] - box[1]) - (y1 - y0) * sc) / 2
        P = [((x - x0) * sc + ox, (y - y0) * sc + oy) for x, y in xy]
        g = ease(t, 0.5, 2.0)
        n = max(2, int(len(P) * g))
        seg = [(x * S, y * S) for x, y in P[:n]]
        def draw(dr):
            dr.line(seg, fill=self.inkA(0.22), width=int(44 * S), joint='curve')
            dr.line(seg, fill=self.ink, width=int(16 * S), joint='curve')
            if g < 1:
                hx, hy = P[n - 1]
                self.tri(dr, hx, hy, 22, fill=self.acc)
        self.put(t, 0.45, draw, rise=0, dur=0.2)
        cnt, _, rest = d['body'].partition('×')
        def foot(dr):
            f = font('display', 170)
            self.text(dr, (MX - 4, 990), f'{cnt}×', f, self.acc)
            x = MX + tw(f'{cnt}×', f) + 26
            self.body(dr, rest.strip(), 1050, 42, x=x, max_w=W - MX - x)
        self.put(t, 1.6, foot)

    def m_trend(self, t, d):
        self.put(t, 0.1, lambda dr: self.kicker(dr, d['kicker']))
        self.put(t, 0.22, lambda dr: self.headline(dr, d['headline'], 226))
        n = d['delta']
        ds = fmt_number(n, ease_expo(t, 0.45, 1.6))
        self.put(t, 0.42, lambda dr: self.text(dr, (MX - 4, 330), ds, font('display', 250), self.acc), rise=50)
        ser = d['series']
        vals = [v for _, v in ser]
        lo, hi = min(vals), max(vals)
        pad = (hi - lo) * 0.18 or 1
        lo, hi = lo - pad, hi + pad
        d0 = dt.date.fromisoformat(ser[0][0][:10])
        d1 = dt.date.fromisoformat(ser[-1][0][:10])
        span = max(1, (d1 - d0).days)
        box = (MX + 10, 650, W - MX - 10, 990)
        P = [(box[0] + (dt.date.fromisoformat(s[:10]) - d0).days / span * (box[2] - box[0]),
              box[3] - (v - lo) / (hi - lo) * (box[3] - box[1])) for s, v in ser]
        g = ease(t, 0.7, 1.8)
        k = max(2, int(len(P) * g))
        def chart(dr):
            area = [(x * S, y * S) for x, y in P[:k]] + [(P[k - 1][0] * S, box[3] * S), (P[0][0] * S, box[3] * S)]
            dr.polygon(area, fill=self.inkA(0.14))
            dr.line([(x * S, y * S) for x, y in P[:k]], fill=self.ink, width=int(9 * S), joint='curve')
            dr.line([box[0] * S, box[3] * S, box[2] * S, box[3] * S], fill=self.inkA(0.5), width=int(2 * S))
            self.tri(dr, P[0][0], P[0][1] - 4, 16, fill=self.ink)
            self.text(dr, (P[0][0], P[0][1] - 30), d['start_label'], font('display', 64), self.ink, 'ls')
            if g >= 1:
                self.tri(dr, P[-1][0], P[-1][1] - 4, 22, fill=self.acc)
                self.text(dr, (P[-1][0], P[-1][1] - 34), d['end_label'], font('display', 72), self.acc, 'rs')
        self.put(t, 0.65, chart, rise=0, dur=0.25)
        def months(dr):
            m = d0.replace(day=1)
            f = font('body', 34, 500)
            while m <= d1:
                x = box[0] + (m - d0).days / span * (box[2] - box[0])
                if box[0] - 5 <= x <= box[2]:
                    self.text(dr, (x, box[3] + 18), 'JFMAMJJASOND'[m.month - 1], f, self.inkA(0.75), 'mt')
                m = (m.replace(day=28) + dt.timedelta(days=5)).replace(day=1)
        self.put(t, 0.9, months, rise=10)
        self.put(t, 1.5, lambda dr: self.body(dr, d['body'], 1078, TYPE['body']))

    def m_records(self, t, d):
        self.put(t, 0.1, lambda dr: self.kicker(dr, d['kicker']))
        self.put(t, 0.22, lambda dr: self.headline(dr, d['headline'], 226))
        rows = d['rows'][:3]
        y = 380
        hgt, gap = 208, 30
        for k, r in enumerate(rows):
            yy = y + k * (hgt + gap)
            def card(dr, r=r, yy=yy):
                self.rrect(dr, (MX, yy, W - MX, yy + hgt), 34, fill=self.ink)
                self.tri(dr, MX + 54, yy + 58, 16, fill=self.acc if self.acc != self.ink else self.bg)
                fs = fit(r['value'], 'display', 168, 470, 90)
                room = (W - 2 * MX) - tw(r['value'], font('display', fs)) - 170
                ls = fit(r['label'].upper(), 'body', 38, room, 34, 600)
                lab = r['label'].upper()
                while tw(lab, font('body', ls, 600)) > room and ' ' in lab:
                    lab = lab.rsplit(' ', 1)[0]
                self.text(dr, (MX + 86, yy + 58), lab, font('body', ls, 600), self.bg, 'lm')
                self.text(dr, (MX + 40, yy + 150), r['date'], font('body', 38, 400), self.bg[:3] + (220,), 'lm')
                self.text(dr, (W - MX - 40, yy + hgt / 2 + 6), r['value'], font('display', fs), self.bg, 'rm')
            self.put(t, 0.5 + 0.22 * k, card, rise=70)

    def m_calendar(self, t, d):
        self.put(t, 0.1, lambda dr: self.kicker(dr, d['kicker']))
        self.put(t, 0.22, lambda dr: self.headline(dr, d['headline'], 226))
        active = set(d['active'])
        start, end = dt.date.fromisoformat(d['start']), dt.date.fromisoformat(d['end'])
        months = end.month
        top, rowh = 372, min(56, 620 / months)
        x0, cw = MX + 58, (W - 2 * MX - 58) / 31
        fl = font('body', 34, 600)
        for m in range(1, months + 1):
            yy = top + (m - 1) * rowh
            def row(dr, m=m, yy=yy):
                self.text(dr, (MX, yy + rowh / 2), 'JFMAMJJASOND'[m - 1], fl, self.inkA(0.85), 'lm')
                day = dt.date(start.year, m, 1)
                while day.month == m and day <= end:
                    cx = x0 + (day.day - 0.5) * cw
                    if day.isoformat() in active:
                        self.tri(dr, cx, yy + rowh / 2 + 2, cw * 0.46, fill=self.acc)
                    else:
                        self.tri(dr, cx, yy + rowh / 2 + 2, cw * 0.2, fill=self.inkA(0.3))
                    day += dt.timedelta(days=1)
            self.put(t, 0.45 + 0.08 * m, row, dur=0.35, rise=16)
        self.put(t, 1.5, lambda dr: self.body(dr, d['body'], top + months * rowh + 34, TYPE['body']))

    def m_clock(self, t, d):
        self.put(t, 0.1, lambda dr: self.kicker(dr, d['kicker']))
        self.put(t, 0.22, lambda dr: self.headline(dr, d['headline'], 226))
        cx, cy, r0, r1 = W / 2, 712, 128, 320
        hrs = d['hours']
        mx = max(hrs) or 1
        g = ease(t, 0.5, 1.4)
        def dial(dr):
            dr.ellipse([(cx - r0 + 8) * S, (cy - r0 + 8) * S, (cx + r0 - 8) * S, (cy + r0 - 8) * S], outline=self.inkA(0.45), width=int(3 * S))
            for h in range(24):
                a = -math.pi / 2 + h / 24 * 2 * math.pi
                L = (r1 - r0) * (hrs[h] / mx) * g
                if hrs[h] == 0:
                    L = 0
                w_ = 0.11
                base1 = (cx + r0 * math.cos(a - w_), cy + r0 * math.sin(a - w_))
                base2 = (cx + r0 * math.cos(a + w_), cy + r0 * math.sin(a + w_))
                tip = (cx + (r0 + 14 + L) * math.cos(a), cy + (r0 + 14 + L) * math.sin(a))
                col = self.acc if h == d['peak'] else self.inkA(0.85)
                dr.polygon([(p[0] * S, p[1] * S) for p in (base1, tip, base2)], fill=col)
            f = font('body', 34, 600)
            for h, lab in ((0, '12 AM'), (6, '6 AM'), (12, '12 PM'), (18, '6 PM')):
                a = -math.pi / 2 + h / 24 * 2 * math.pi
                rr = r1 + 52
                self.text(dr, (cx + rr * math.cos(a), cy + rr * math.sin(a)), lab, f, self.inkA(0.9), 'mm')
            self.text(dr, (cx, cy + 6), d['label'], font('display', fit(d['label'], 'display', 104, 2 * r0 - 30)), self.acc, 'mm')
        self.put(t, 0.45, dial, rise=0, dur=0.3)
        self.put(t, 1.4, lambda dr: self.body(dr, d['body'], 1112, TYPE['body'], anchor='ma'))

    def m_versus(self, t, d):
        self.put(t, 0.1, lambda dr: self.kicker(dr, d['kicker']))
        self.put(t, 0.22, lambda dr: self.headline(dr, d['headline'], 226))
        L, R = d['left'], d['right']
        lv = int(round(L['value'] * ease_expo(t, 0.45, 1.3)))
        rv = int(round(R['value'] * ease_expo(t, 0.75, 1.3)))
        self.put(t, 0.45, lambda dr: (self.text(dr, (290, 640), str(lv), font('display', 320), self.ink, 'ms'),
                                      self.text(dr, (290, 700), L['label'].upper(), font('body', 40, 600), self.inkA(0.9), 'ms')), rise=50)
        self.put(t, 0.75, lambda dr: (self.text(dr, (790, 640), str(rv), font('display', 320), self.acc, 'ms'),
                                      self.text(dr, (790, 700), R['label'].upper(), font('body', 40, 600), self.inkA(0.9), 'ms')), rise=50)
        self.put(t, 1.0, lambda dr: self.tri(dr, 540, 520, 46, fill=self.ink, rot=math.pi / 2), rise=0)
        self.put(t, 1.4, lambda dr: self.body(dr, d['body'], 800, TYPE['body'], anchor='ma', max_w=860))

    def m_zones(self, t, d):
        self.put(t, 0.1, lambda dr: self.kicker(dr, d['kicker']))
        self.put(t, 0.22, lambda dr: self.headline(dr, d['headline'], 226))
        z = d['zones']
        mx = max(z) or 1
        top = max(range(5), key=lambda i: z[i])
        for k in range(5):
            y = 400 + k * 118
            g = ease(t, 0.5 + 0.12 * k, 1.0)
            def bar(dr, k=k, y=y, g=g):
                self.text(dr, (MX, y + 44), f'Z{k + 1}', font('display', 72), self.ink, 'lm')
                x0 = MX + 100
                L = (640 - 40) * z[k] / mx * g + 40
                col = self.acc if k == top else self.inkA(0.8)
                dr.polygon([(x0 * S, y * S), ((x0 + L - 40) * S, y * S), ((x0 + L) * S, (y + 44) * S),
                            ((x0 + L - 40) * S, (y + 88) * S), (x0 * S, (y + 88) * S)], fill=col)
                self.text(dr, (x0 + L + 20, y + 46), f'{z[k] * g:,.0f} h', font('body', 38, 600), self.ink, 'lm')
            self.put(t, 0.5 + 0.12 * k, bar, rise=0, dur=0.2)
        self.put(t, 1.5, lambda dr: self.body(dr, d['body'], 1020, 42))

    def m_persona(self, t, d):
        self.put(t, 0.1, lambda dr: self.kicker(dr, d['kicker'], 300))
        name = d['name'].upper()
        f = font('display', 200)
        lines = wrap(name, f, W - 2 * MX)
        size = 200
        if len(lines) > 2:
            size = 150
            lines = wrap(name, font('display', size), W - 2 * MX)
        size = min(size, min(fit(ln, 'display', size, W - 2 * MX, 110) for ln in lines))
        for k, ln in enumerate(lines):
            self.put(t, 0.3 + 0.18 * k, lambda dr, k=k, ln=ln: self.text(dr, (MX - 4, 356 + k * size * 0.88), ln, font('display', size), self.acc if k == len(lines) - 1 else self.ink), rise=60)
        by = 356 + len(lines) * size * 0.88 + 40
        self.put(t, 0.9, lambda dr: self.body(dr, d['body'], by, TYPE['body']))
        py = by + 42 * 1.22 * len(wrap(d['body'], font('body', TYPE['body']), W - 2 * MX)) + 50
        x = MX
        fp = font('body', 38, 600)
        for k, tr in enumerate(d.get('traits', [])):
            w_ = tw(tr, fp) + 64
            if x + w_ > W - MX:
                x, py = MX, py + 96
            def pill(dr, x=x, py=py, tr=tr, w_=w_):
                self.rrect(dr, (x, py, x + w_, py + 76), 38, outline=self.ink, width=3)
                self.text(dr, (x + w_ / 2, py + 39), tr, fp, self.ink, 'mm')
            self.put(t, 1.2 + 0.12 * k, pill, rise=20)
            x += w_ + 18

    def m_cta(self, t, d):
        cx, cy, R = W / 2, 420, 170
        g = ease(t, 0.15, 0.7)
        def avatar(dr):
            av = Image.open(os.path.join(HERE, 'assets', 'avatar.jpg')).convert('RGB')
            rr = R * (0.6 + 0.4 * g)
            D = int(2 * rr * S)
            av = av.resize((D, D), Image.LANCZOS)
            m = Image.new('L', (D, D), 0)
            ImageDraw.Draw(m).ellipse([0, 0, D - 1, D - 1], fill=255)
            self.img.paste(av, (int((cx - rr) * S), int((cy - rr) * S)), m)
            dr.ellipse([(cx - rr - 9) * S, (cy - rr - 9) * S, (cx + rr + 9) * S, (cy + rr + 9) * S], outline=self.ink, width=int(8 * S))
        self.put(t, 0.15, avatar, rise=0, dur=0.3)
        l1, l2 = [s.upper() for s in d['title']]
        size = min(fit(l1, 'display', 128, 920), fit(l2, 'display', 128, 920))
        self.put(t, 0.5, lambda dr: self.text(dr, (W / 2, 735), l1, font('display', size), self.ink, 'ms'))
        self.put(t, 0.65, lambda dr: self.text(dr, (W / 2, 735 + size * 0.88), l2, font('display', size), self.acc, 'ms'))
        self.put(t, 0.85, lambda dr: self.body(dr, d['body'], 872, TYPE['body'], anchor='ma'))
        fp = font('body', 38, 600)
        pills = [f'{a}  {b}' for a, b in d['handles']]
        ws = [tw(p, fp) + 56 for p in pills]
        rows = [pills] if sum(ws) + 16 * (len(ws) - 1) <= W - 2 * MX else [pills[:2], pills[2:]]
        y = 950
        k = 0
        for row in rows:
            rw = sum(tw(p, fp) + 56 for p in row) + 16 * (len(row) - 1)
            x = (W - rw) / 2
            for p in row:
                w_ = tw(p, fp) + 56
                def pill(dr, x=x, y=y, p=p, w_=w_):
                    self.rrect(dr, (x, y, x + w_, y + 74), 37, fill=self.ink)
                    self.text(dr, (x + w_ / 2, y + 38), p, fp, self.bg, 'mm')
                self.put(t, 1.05 + 0.1 * k, pill, rise=20)
                x += w_ + 16
                k += 1
            y += 90
        self.put(t, 1.5, lambda dr: self.text(dr, (W / 2, y + 30), d['site'], font('body', 40, 500), self.inkA(0.9), 'ms'))


# ============================================================================================ output
def bg_still(i):
    p = os.path.join(BG_DIR, f'bg_{i + 1:02d}.jpg')
    if not os.path.exists(p):
        p = p[:-4] + '.png'
    if os.path.exists(p):
        im = Image.open(p).convert('RGB')
        return im if im.size == (W * S, H * S) else im.resize((W * S, H * S), Image.LANCZOS)
    return Image.new('RGB', (W * S, H * S), hexrgb(TOK['slides'][i]['bg'])[:3])


def ffmpeg_exe():
    exe = shutil.which('ffmpeg')
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def video_backend():
    exe = ffmpeg_exe()
    if exe:
        return 'ffmpeg', exe
    try:
        import cv2, numpy  # noqa: F401
        return 'opencv', None
    except Exception:
        return None, None


NO_VIDEO = """VIDEO: NOT POSSIBLE YET — no ffmpeg and no OpenCV in this environment.
Fix (try in this order, then run --check again):
  1. pip install imageio-ffmpeg
  2. no internet? download https://garmin.vaw.be/wrapped/vendor/imageio_ffmpeg-0.7.0-py3-none-manylinux2014_x86_64.whl
     (or ask the user to download and upload it) and run: pip install <that .whl file>
Never hand over PNGs instead of the MP4s the user asked for."""


def check():
    import platform
    import PIL
    print(f'python {platform.python_version()} · Pillow {PIL.__version__}')
    ok = all(os.path.exists(os.path.join(FONT_DIR, f)) for f in TOK['fonts'].values())
    bgs = sum(os.path.exists(os.path.join(BG_DIR, f'bg_{i:02d}.mp4')) for i in range(1, 11))
    print(f'fonts: {"OK" if ok else "MISSING"} · background loops: {bgs}/10 · background stills: '
          f'{sum(os.path.exists(os.path.join(BG_DIR, f"bg_{i:02d}.jpg")) for i in range(1, 11))}/10')
    backend, exe = video_backend()
    if backend == 'ffmpeg':
        print(f'VIDEO: OK (ffmpeg: {exe})')
    elif backend == 'opencv':
        print('VIDEO: OK (OpenCV fallback)')
    else:
        print(NO_VIDEO)
    return 0 if backend and ok and bgs == 10 else 2


def write_video(i, overlay, path):
    """MP4 1080x1350: the 6 s seamless background loop with the static data layer on top. Loops on its own."""
    backend, exe = video_backend()
    if not backend:
        raise SystemExit(NO_VIDEO)
    bgp = os.path.join(BG_DIR, f'bg_{i + 1:02d}.mp4')
    if backend == 'ffmpeg':
        ovp = path[:-4] + '_overlay.png'
        overlay.save(ovp)
        if os.path.exists(bgp):
            src = ['-i', bgp]
        else:  # no loop file: hold the still (no motion, but still a valid clip)
            src = ['-loop', '1', '-framerate', str(FPS), '-t', str(SECONDS), '-i', os.path.join(BG_DIR, f'bg_{i + 1:02d}.jpg')]
        cmd = [exe, '-v', 'error', '-y', *src, '-i', ovp, '-filter_complex',
               f'[0:v]scale={W}:{H},setsar=1[b];[b][1:v]overlay=0:0,format=yuv420p[v]', '-map', '[v]',
               '-t', str(SECONDS), '-r', str(FPS), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
               '-movflags', '+faststart', '-an', path]
        subprocess.run(cmd, check=True)
        os.remove(ovp)
    else:
        import cv2
        import numpy as np
        ov = np.asarray(overlay).astype(np.float32)
        alpha, rgb = ov[:, :, 3:4] / 255.0, ov[:, :, :3][:, :, ::-1]
        frames = []
        cap = cv2.VideoCapture(bgp) if os.path.exists(bgp) else None
        while cap is not None:
            ok, fr = cap.read()
            if not ok:
                break
            frames.append(cv2.resize(fr, (W, H)))
        if not frames:
            still = np.asarray(bg_still(i).resize((W, H)))[:, :, ::-1]
            frames = [still] * (FPS * SECONDS)
        vw = None
        for codec in ('avc1', 'mp4v'):
            vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*codec), FPS, (W, H))
            if vw.isOpened():
                break
        for fr in frames[:FPS * SECONDS]:
            vw.write((fr * (1 - alpha) + rgb * alpha).astype(np.uint8))
        vw.release()
    if not (os.path.exists(path) and os.path.getsize(path) > 10000):
        raise SystemExit(f'Video failed for slide {i + 1}: {path} was not written.')


SPORT_TAGS = {'running': 'running', 'cycling': 'cycling', 'swimming': 'swimming', 'walking': 'walking', 'hiking': 'hiking',
              'strength': 'strengthtraining', 'hiit': 'hiit', 'yoga': 'yoga', 'rowing': 'rowing', 'paddle': 'kayaking',
              'racket': 'padel', 'skiing': 'skiing', 'cardio': 'cardio', 'multisport': 'triathlon', 'golf': 'golf',
              'surfing': 'surfing', 'climbing': 'climbing'}


def captions(plan):
    """Instagram + TikTok captions built from the computed numbers (the assistant may reword, never renumber)."""
    meta, slides = plan['meta'], plan['slides']
    yy = str(meta.get('year', 2026))[2:]
    by = {s.get('key', ''): s for s in slides}
    facts, sport = [], None
    intro = by.get('intro')
    if intro:
        facts.append(f"{fmt_number(intro['hook']['number'], 1)} {intro['hook']['unit']}")
    hero = next((s for s in slides if s.get('key', '').startswith('hero_')), None)
    if hero:
        sport = hero['key'][5:]
        if hero.get('unit') == 'hours':  # non-distance sport: "146 hours of strength"
            facts.append(f"{fmt_number(hero['number'], 1)} hours of {hero['kicker'].split(' · ')[0].lower()}")
        else:                            # "I ran 1,198 km"
            facts.append(f"{hero['headline']} {fmt_number(hero['number'], 1)} {hero.get('unit', '')}".strip())
    if 'records' in by and by['records'].get('rows'):
        r = by['records']['rows'][0]
        hl = by['records']['headline'].replace('My ', '')
        if hl.lower().startswith('fastest'):
            facts.append(f"Fastest {r['label']}: {r['value']}")
        else:                            # "Longest ride: 120 km"
            facts.append(f"{hl[:1].upper()}{hl[1:].rstrip('s')}: {r['value']}")
    if 'calendar' in by:
        facts.append(by['calendar']['headline'])
    if 'vo2max' in by:
        facts.append(f"VO2 max {fmt_number(by['vo2max']['delta'], 1)}")
    if 'route' in by:
        facts.append(by['route']['body'].replace('×', '× my go-to'))
    persona = by.get('persona', {}).get('name')
    tags = ['#garminwrapped', f'#garminwrapped20{yy}', '#garmin']
    if sport in SPORT_TAGS:
        tags.append('#' + SPORT_TAGS[sport])
    so_far = '' if str(meta.get('period', '')).isdigit() else ' (so far)'
    ig = '\n'.join([
        f"My Garmin Wrapped '{yy}{so_far} is here ⌚",
        '',
        *[f'▲ {f}' for f in facts[:5]],
        *([f'▲ Training personality: {persona}'] if persona else []),
        '',
        'Swipe through my year 👉',
        '',
        'Made with the Garmin School prompt (@vawbe). Make your own for free: garmin.vaw.be/en/wrapped',
        '',
        ' '.join(tags + ['#yearinreview', '#garminschool', '#fitness']),
    ])
    tt_facts = ', '.join(facts[:2])
    tt = (f"My Garmin Wrapped '{yy}{so_far}: {tt_facts}" + (f" and apparently I'm {persona.replace('The ', 'the ', 1)} 😅" if persona else '.') +
          ' Made with the Garmin School prompt (@vaw.be) ' + ' '.join(tags + ['#fitnesstok', '#fyp']))
    return ig, tt


def write_captions(plan, out):
    ig, tt = captions(plan)
    p = os.path.join(out, 'captions.txt')
    with open(p, 'w', encoding='utf-8') as fh:
        fh.write('INSTAGRAM\n\n' + ig + '\n\n\nTIKTOK\n\n' + tt + '\n')
    print('captions', p, flush=True)
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('plan', nargs='?')
    ap.add_argument('--out', default='garmin_wrapped_out')
    ap.add_argument('--stills', action='store_true', help='PNG 2160x2700 per slide')
    ap.add_argument('--video', action='store_true', help='MP4 1080x1350 per slide, 6 s seamless loop (+ the PNGs as a backup)')
    ap.add_argument('--slides', type=int, nargs='*')
    ap.add_argument('--sheet', action='store_true', help='contact_sheet.png with all slides, to check the result')
    ap.add_argument('--check', action='store_true', help='check fonts, backgrounds and video support, then exit')
    a = ap.parse_args()
    if a.check:
        sys.exit(check())
    if not a.plan:
        ap.error('give the path to wrapped.json')
    if not (a.stills or a.video):
        a.stills = True
    if a.video and video_backend()[0] is None:
        raise SystemExit(NO_VIDEO)
    plan = json.load(open(a.plan))
    slides = plan['slides']
    os.makedirs(a.out, exist_ok=True)
    write_captions(plan, a.out)  # always: Instagram + TikTok captions with the real numbers
    which = [k - 1 for k in (a.slides or range(1, len(slides) + 1))]
    year = str(plan['meta'].get('year', 2026))[2:]
    for i in which:
        sl = Slide(i, slides[i], len(slides))
        name = os.path.join(a.out, f'garmin_wrapped_{year}_{i + 1:02d}')
        layer = sl.render(99)
        im = bg_still(i)
        im.paste(layer, (0, 0), layer)
        # PNG always: with --video the stills come along as a backup (Wim, 2026-11-20)
        im.save(name + '.png', optimize=True)
        print('png', name + '.png', flush=True)
        if a.video:
            write_video(i, layer.resize((W, H), Image.LANCZOS), name + '.mp4')
            print('mp4', name + '.mp4', flush=True)
    if a.sheet:
        ims = []
        for i in range(len(slides)):
            base = os.path.join(a.out, f'garmin_wrapped_{year}_{i + 1:02d}')
            p = base + '.png'
            if os.path.exists(p):
                ims.append(Image.open(p).convert('RGB').resize((W // 3, H // 3)))
        if ims:
            sheet = Image.new('RGB', (len(ims) * W // 3, H // 3))
            for k, im in enumerate(ims):
                sheet.paste(im, (k * W // 3, 0))
            sheet.save(os.path.join(a.out, 'contact_sheet.png'))
            print('sheet', os.path.join(a.out, 'contact_sheet.png'))


if __name__ == '__main__':
    main()
