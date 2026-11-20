# Garmin Wrapped '26 — style guide ("Prism")

The look of the Garmin School year-in-review carousel. The kit (`kit/wrapped.py`) applies all of this
automatically. This page is for Wim, and for any agent that has to adapt a slide by hand.

## Idea

A year of training is a spectrum. The ten slides walk through ten saturated colours, one per slide, and
the colour **flows across every seam**: the background blends into the next slide's colour and a 3D
shape always sits half on one slide and half on the next. Swiping feels like one long panorama.

The motif is the **triangle**: a nod to the navigation delta every Garmin user knows, never the logo itself.
Rounded 3D prisms, triangle rings, tetrahedra and triangle confetti in the background (three.js, GSAP
motion), and triangles in the data layer: bullets, chart markers, the calendar grid, the podium, the
progress indicator, the play-arrow on the fitness-age slide. (Not in the Garmin School pill and not around
the avatar: those stay clean.)

## Format

- 4:5, artboard 1080 × 1350 (the Garmin School carousel format), one carousel for Instagram and TikTok.
- Stills: PNG 2160 × 2700. Animated: one MP4 per slide, 1080 × 1350, 25 fps, 6 s, looping seamlessly on its own
  (no combined reel: post the ten clips as one carousel).
- Ten slides: 1 intro, 2–9 data (picked per athlete), 10 call to action.

## Colour (per slide, `kit/style/tokens.json`)

| # | background | 3D shape | ink | accent |
|---|---|---|---|---|
| 1 | electric violet `#4B1FD1` | hot pink `#FF3D8B` | white | lime `#C6F432` |
| 2 | hot pink `#FF2E88` | sun `#FFD23F` | white | `#FFE15C` |
| 3 | orange `#FF6B1A` | violet `#4B1FD1` | night `#1A0B2E` | deep violet `#2B0E7A` |
| 4 | sun yellow `#FFD23F` | cobalt `#2B4BFF` | `#141414` | cobalt |
| 5 | lime `#B8F23C` | purple `#7A2BE2` | `#141414` | `#5B1CC4` |
| 6 | mint `#18C79A` | pink `#FF3D8B` | `#08231B` | `#08231B` |
| 7 | sky `#1FB6FF` | orange `#FF6B1A` | `#06192A` | `#06192A` |
| 8 | cobalt `#2B4BFF` | lime `#C6F432` | white | lime |
| 9 | purple `#8A2BE2` | amber `#FFB21F` | white | `#FFD23F` |
| 10 | night `#13101F` | pink + lime + all | white | lime |

Rules: text is always **ink or accent on the slide's own background**. A key number is in the accent colour.
Never place text on a 3D shape except the intro title. A fine film grain sits on every background.

## Type (Garmin School carousel rules: never go small)

| role | font | size (on 1080 px) |
|---|---|---|
| intro title "GARMIN / WRAPPED '26" | Bebas Neue | up to 230 |
| hero number | Bebas Neue | up to 340 (auto-fits the width) |
| headline | Bebas Neue, uppercase | 84–112 |
| unit under a number | Bebas Neue | 104 |
| body | Geist Regular, line height 1.22 (same as the Garmin School carousels) | 42 |
| kicker above a headline | Geist SemiBold, uppercase, +2 tracking | 36 |
| stat labels, month letters, dial labels | Geist Medium/SemiBold | 34 |
| pills (traits, handles), dates, sub-labels | Geist SemiBold | 38–40 |
| slide 1 footer ("Swipe through my year →") | Geist Medium, arrow scaled with it | 46, second line 38 |
| "BY THE GARMIN SCHOOL" tag | Geist SemiBold, uppercase | 34 |

**Minimum size anywhere: 34 px** (on the 1080 px artboard). If text doesn't fit, the kit shrinks it to the minimum and then wraps it; it
never cuts a value.

## Layout

- Margins 80 px left/right.
- Top bar on **every** slide: the `BY THE GARMIN SCHOOL` pill top-left (text only, no icon) (ink fill, background-coloured text)
  and ten small triangles top-right showing the position (current one filled).
- Kicker at y 178, headline at y 226, content from y ~330 to ~1150.
- The bottom band (y > 1150) belongs to the seam shapes and confetti: no text there except the intro footer.
- Slide 1 has the word "Garmin" (in the title), one hook stat and a two-line footer with the arrow →
  after line 1 (the Garmin School carousel rule).
- Slide 10: avatar in a plain circle with an ink ring (no triangle around it), "MAKE YOUR OWN / GARMIN WRAPPED", "Free prompt from the Garmin
  School", pills with Instagram @vawbe · TikTok @vaw.be · YouTube @vawbe, and garmin.vaw.be.

## Motion (animated version)

- Only the background moves (Wim, 2026-11-20): the three.js strip loops seamlessly every 6 s, shapes wobble
  and drift with GSAP sine yoyos, confetti orbits and spins.
- The data layer (text, numbers, charts, avatar) is **static**: no build-in, no build-out. Every MP4 is exactly
  one 6 s background loop, so it loops seamlessly on its own on Instagram and TikTok.
- One MP4 per slide (1080 × 1350, 25 fps, H.264), never one combined reel.

## Slide modules

| module | used for |
|---|---|
| `intro` | title, hook stat (hours of training, else steps) |
| `big_number` | top sport distance/hours, sleep hours, steps, floors, workouts, calories, intensity minutes |
| `podium` | top 3 sports by hours |
| `records` | fastest 1K/mile/5K/10K/half/marathon, or the longest sessions for non-runners |
| `route` | the most repeated route, line only (first/last 200 m removed) |
| `calendar` | every active day as a triangle, longest streak, busiest month |
| `clock` | 24-hour dial of start times, the "power hour" |
| `trend` | VO2 max (or resting heart rate) through the year |
| `versus` | real age vs fitness age |
| `zones` | time in heart-rate zones |
| `persona` | training personality: Early Bird, Night Owl, Hybrid Athlete, Streak Machine, Weekend Warrior, Base Builder, the {Sport} Purist, All-Rounder |
| `cta` | make your own |

## Don'ts

- No official Garmin logos or the exact Garmin delta; triangles are always rounded and playful.
- No maps, addresses, coordinates or route start/finish points.
- No weight, BMI, body composition, menstrual or food data.
- No invented numbers: every value comes from the user's Garmin data.
