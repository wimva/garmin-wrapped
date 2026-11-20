#!/usr/bin/env python3
"""Garmin Wrapped '26 — step 2: turn normalized Garmin data into a 10-slide plan (wrapped.json).

    python compute.py DATA_DIR                 # writes DATA_DIR/wrapped.json and prints a summary
    python compute.py DATA_DIR --plan          # only prints which activity routes (polylines) to fetch

DATA_DIR holds the normalized files described in SCHEMA.md (activities.json, daily.json, sleep.json,
vo2max.json, hrv.json, profile.json, routes/<activity_id>.json). Missing files are fine: modules that
need them are skipped, so every athlete still gets 8 strong middle slides.
Pure Python 3 standard library.
"""
import json, math, os, sys, datetime as dt
from collections import Counter, defaultdict

# ----------------------------------------------------------------------------------------------- sports
FAMILIES = {
    'running': ['running', 'trail_running', 'treadmill_running', 'track_running', 'indoor_running', 'street_running', 'ultra_run', 'virtual_run'],
    'cycling': ['cycling', 'road_biking', 'mountain_biking', 'gravel_cycling', 'indoor_cycling', 'virtual_ride', 'e_bike_fitness',
                'e_bike_mountain', 'cyclocross', 'track_cycling', 'bmx', 'recumbent_cycling', 'hand_cycling', 'bike_commute', 'e_bike'],
    'swimming': ['swimming', 'lap_swimming', 'open_water_swimming'],
    'walking': ['walking', 'casual_walking', 'speed_walking', 'indoor_walking'],
    'hiking': ['hiking', 'mountaineering', 'rucking'],
    'strength': ['strength_training', 'weightlifting'],
    'hiit': ['hiit', 'boxing', 'mixed_martial_arts', 'jump_rope', 'crossfit'],
    'yoga': ['yoga', 'pilates', 'breathwork', 'meditation', 'mobility'],
    'rowing': ['rowing', 'indoor_rowing', 'rowing_v2'],
    'paddle': ['kayaking', 'stand_up_paddleboarding', 'canoeing', 'whitewater_rafting_kayaking'],
    'racket': ['padel', 'tennis', 'pickleball', 'badminton', 'squash', 'table_tennis', 'racquetball', 'platform_tennis'],
    'skiing': ['resort_skiing', 'resort_skiing_snowboarding', 'backcountry_skiing', 'cross_country_skiing', 'skate_skiing', 'snowboarding', 'resort_snowboarding'],
    'cardio': ['indoor_cardio', 'fitness_equipment', 'elliptical', 'stair_climbing', 'floor_climbing', 'stairstepper'],
    'multisport': ['multi_sport', 'triathlon', 'duathlon'],
    'golf': ['golf'],
    'surfing': ['surfing', 'kitesurfing', 'windsurfing', 'wakeboarding'],
    'climbing': ['bouldering', 'indoor_climbing', 'rock_climbing'],
}
NAMES = {'running': 'Running', 'cycling': 'Cycling', 'swimming': 'Swimming', 'walking': 'Walking', 'hiking': 'Hiking',
         'strength': 'Strength', 'hiit': 'HIIT', 'yoga': 'Yoga & mobility', 'rowing': 'Rowing', 'paddle': 'Paddling',
         'racket': 'Racket sports', 'skiing': 'Skiing', 'cardio': 'Cardio', 'multisport': 'Multisport', 'golf': 'Golf',
         'surfing': 'Water sports', 'climbing': 'Climbing'}
DISTANCE_SPORTS = {'running', 'cycling', 'swimming', 'walking', 'hiking', 'rowing', 'paddle', 'skiing'}
VERB = {'running': 'ran', 'cycling': 'rode', 'swimming': 'swam', 'walking': 'walked', 'hiking': 'hiked', 'rowing': 'rowed',
        'paddle': 'paddled', 'skiing': 'skied'}
KEY2FAM = {k: fam for fam, keys in FAMILIES.items() for k in keys}


def family(key):
    key = (key or '').lower().replace(' ', '_').replace('-', '_')
    if key in KEY2FAM:
        return KEY2FAM[key]
    for fam, keys in FAMILIES.items():
        if any(k in key for k in keys) or fam in key:
            return fam
    return key or 'other'


def fam_name(f):
    return NAMES.get(f, f.replace('_', ' ').title())


# ----------------------------------------------------------------------------------------------- utils
def load(d, name, default):
    p = os.path.join(d, name)
    if not os.path.exists(p):
        return default
    with open(p) as fh:
        return json.load(fh)


def num(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def d(s):
    return dt.date.fromisoformat(str(s)[:10])


def fmt_int(v):
    return f'{int(round(v)):,}'


def fmt_time(sec):
    sec = int(round(sec))
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'


def plural(n, w):
    return f'{w}' if round(n) == 1 else f'{w}s'


def hav(a, b):
    R = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    x = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))


MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']


# ----------------------------------------------------------------------------------------------- core
class Year:
    def __init__(self, data_dir):
        self.dir = data_dir
        prof = load(data_dir, 'profile.json', {})
        self.prof = prof
        self.imperial = str(prof.get('units', 'metric')).lower().startswith('imp')
        today = dt.date.today()
        self.year = int(prof.get('year', today.year))
        self.start = dt.date(self.year, 1, 1)
        self.end = d(prof['end_date']) if prof.get('end_date') else min(today, dt.date(self.year, 12, 31))
        self.name = (prof.get('first_name') or '').strip()

        acts = []
        for a in load(data_dir, 'activities.json', []):
            try:
                day = d(a.get('date') or a.get('start_local'))
            except Exception:
                continue
            if not (self.start <= day <= self.end):
                continue
            a = dict(a)
            a['_day'] = day
            a['_fam'] = family(a.get('sport'))
            a['_dur'] = num(a.get('duration_s')) or 0.0
            a['_dist'] = num(a.get('distance_m')) or 0.0
            acts.append(a)
        self.acts = sorted(acts, key=lambda a: a.get('start_local') or str(a['_day']))
        self.daily = [x for x in load(data_dir, 'daily.json', []) if self._in(x)]
        self.sleep = [x for x in load(data_dir, 'sleep.json', []) if self._in(x)]
        self.vo2 = sorted([x for x in load(data_dir, 'vo2max.json', []) if self._in(x) and num(x.get('value'))], key=lambda x: x['date'])
        self.hrv = sorted([x for x in load(data_dir, 'hrv.json', []) if self._in(x) and num(x.get('value'))], key=lambda x: x['date'])

    def _in(self, x):
        try:
            return self.start <= d(x['date']) <= self.end
        except Exception:
            return False

    # --- units
    def km(self, m):
        return m / (1609.344 if self.imperial else 1000.0)

    @property
    def dunit(self):
        return 'mi' if self.imperial else 'km'

    def elev(self, m):
        return m * 3.28084 if self.imperial else m

    @property
    def eunit(self):
        return 'ft' if self.imperial else 'm'

    @property
    def period(self):
        if self.end >= dt.date(self.year, 12, 31):
            return f'{self.year}'
        return f'Jan 1 – {self.end.strftime("%b")} {self.end.day}, {self.year}'

    # --- aggregates
    def families(self):
        agg = defaultdict(lambda: {'sessions': 0, 'hours': 0.0, 'dist_m': 0.0, 'elev_m': 0.0, 'kcal': 0.0})
        for a in self.acts:
            g = agg[a['_fam']]
            g['sessions'] += 1
            g['hours'] += a['_dur'] / 3600
            g['dist_m'] += a['_dist']
            g['elev_m'] += num(a.get('elevation_gain_m')) or 0
            g['kcal'] += num(a.get('calories')) or 0
        return sorted(agg.items(), key=lambda kv: -kv[1]['hours'])

    def active_days(self):
        return sorted({a['_day'] for a in self.acts})

    def streak(self):
        days = self.active_days()
        best = cur = 0
        prev = None
        for x in days:
            cur = cur + 1 if prev and (x - prev).days == 1 else 1
            best = max(best, cur)
            prev = x
        return best

    def route_clusters(self):
        pts = [a for a in self.acts if num(a.get('start_lat')) and num(a.get('start_lon')) and a['_dist'] > 500]
        clusters = []
        for a in pts:
            p = (num(a['start_lat']), num(a['start_lon']))
            for c in clusters:
                if c['fam'] == a['_fam'] and hav(p, c['p']) < 250 and abs(a['_dist'] - c['dist']) / c['dist'] < 0.08:
                    c['acts'].append(a)
                    break
            else:
                clusters.append({'p': p, 'dist': a['_dist'], 'fam': a['_fam'], 'acts': [a]})
        clusters.sort(key=lambda c: -len(c['acts']))
        return clusters


# ----------------------------------------------------------------------------------------------- modules
def comparisons(y, fam, dist_m, elev_m):
    km = dist_m / 1000
    if fam == 'running':
        return f'That is {km / 42.195:.1f} marathons back to back.', min(int(km // 42.195), 40)
    if fam == 'cycling':
        return f'That is {km / 3400 * 100:.0f}% of a full Tour de France.', None
    if fam == 'swimming':
        return f'That is {km / 33.8:.1f}× across the English Channel.', min(int(km // 33.8), 40) or None
    if fam in ('hiking', 'walking') and elev_m > 3000:
        return f'You climbed {elev_m / 8849:.1f}× Mount Everest on the way.', min(int(elev_m // 8849), 40) or None
    pct = km / 40075 * 100
    if pct >= 1:
        return f'That is {pct:.1f}% of the way around the Earth.', None
    return f'That is {km / 42.195:.1f} marathon distances.', None


def big(value, decimals=0, prefix='', suffix=''):
    return {'value': round(value, decimals), 'decimals': decimals, 'prefix': prefix, 'suffix': suffix}


def build_candidates(y):
    C = []  # (score, slide)
    fams = y.families()
    total_h = sum(f[1]['hours'] for f in fams)
    sessions = len(y.acts)

    # 1. top sport hero (always, if any activity)
    for rank, (fam, g) in enumerate(fams[:2]):
        if g['sessions'] < 3 or (rank == 1 and g['hours'] < 0.2 * total_h):
            continue
        if fam in DISTANCE_SPORTS and g['dist_m'] > 1000:
            line, tri = comparisons(y, fam, g['dist_m'], g['elev_m'])
            s = {'module': 'big_number', 'key': f'hero_{fam}', 'kicker': f'{fam_name(fam)} · {y.period}',
                 'headline': f'I {VERB.get(fam, "moved")}', 'number': big(y.km(g['dist_m'])), 'unit': y.dunit,
                 'body': line, 'tri_count': tri,
                 'stats': [[fmt_int(g['sessions']), plural(g['sessions'], 'session')],
                           [fmt_int(g['hours']), 'hours'],
                           [fmt_int(y.elev(g['elev_m'])), f'{y.eunit} climbed']]}
        else:
            s = {'module': 'big_number', 'key': f'hero_{fam}', 'kicker': f'{fam_name(fam)} · {y.period}',
                 'headline': f'{fam_name(fam)} time', 'number': big(g['hours']), 'unit': 'hours',
                 'body': f'{g["sessions"]} sessions, about {g["hours"] * 60 / g["sessions"]:.0f} minutes each.',
                 'tri_count': min(g['sessions'], 40) if g['sessions'] <= 40 else None,
                 'stats': [[fmt_int(g['sessions']), 'sessions'], [fmt_int(g['kcal']), 'kcal']]}
            if fam == 'strength':
                reps = sum(num(a.get('reps')) or 0 for a in y.acts if a['_fam'] == fam)
                kg = sum(num(a.get('volume_kg')) or 0 for a in y.acts if a['_fam'] == fam)
                if reps:
                    s['stats'].append([fmt_int(reps), 'reps'])
                if kg > 1000:
                    s['body'] = f'I moved {kg / 1000:,.0f} tonnes of weight. One rep at a time.'
        C.append((95 - rank * 30, s))

    # 2. podium
    pod = [f for f in fams if f[1]['sessions'] >= 2][:3]
    if len(pod) >= 2:
        C.append((78, {'module': 'podium', 'key': 'podium', 'kicker': 'Top sports', 'headline': 'My top sports',
                       'items': [{'name': fam_name(f), 'hours': round(g['hours'], 1), 'sessions': g['sessions']} for f, g in pod],
                       'body': f'{sessions} workouts, {total_h:,.0f} hours in total.'}))

    # 3. fastest efforts (running first, then cycling/swim longest)
    runs = [a for a in y.acts if a['_fam'] == 'running']
    rows = []
    for field, label in (('fastest_1k_s', '1K'), ('fastest_mile_s', 'Mile'), ('fastest_5k_s', '5K'),
                         ('fastest_10k_s', '10K'), ('fastest_half_s', 'Half marathon'), ('fastest_marathon_s', 'Marathon')):
        if y.imperial and field == 'fastest_1k_s':
            continue
        if not y.imperial and field == 'fastest_mile_s':
            continue
        c = [(num(a.get(field)), a) for a in runs if num(a.get(field))]
        if c:
            t, a = min(c, key=lambda x: x[0])
            rows.append({'label': label, 'value': fmt_time(t), 'date': a['_day'].strftime('%b %d').replace(' 0', ' ')})
    top_fam = fams[0][0] if fams else None
    if rows and len(runs) >= 5 and (top_fam == 'running' or (len(runs) >= 25 and top_fam not in DISTANCE_SPORTS)):
        rows = (rows[-3:] if len(rows) > 3 else rows)
        C.append((80, {'module': 'records', 'key': 'records', 'kicker': 'Fastest efforts this year', 'headline': 'My fastest runs', 'rows': rows}))
    else:
        # longest session of the top distance sport
        dsp = [a for a in y.acts if a['_fam'] == top_fam and a['_dist'] > 0] if top_fam in DISTANCE_SPORTS else []
        dsp = dsp or [a for a in y.acts if a['_fam'] in DISTANCE_SPORTS and a['_dist'] > 0]
        if len(dsp) >= 5:
            top = sorted(dsp, key=lambda a: -a['_dist'])[:3]
            C.append((76 if top_fam in DISTANCE_SPORTS else 60, {'module': 'records', 'key': 'records', 'kicker': 'Biggest days', 'headline': f'My longest {VERB.get(top_fam, "sessions").replace("rode", "rides").replace("ran", "runs").replace("swam", "swims").replace("walked", "walks").replace("hiked", "hikes").replace("rowed", "rows")}' if top_fam in VERB else 'Longest sessions',
                           'rows': [{'label': (a.get('name') or fam_name(a['_fam']))[:28], 'value': f'{y.km(a["_dist"]):.0f} {y.dunit}' if y.km(a['_dist']) >= 100 else f'{y.km(a["_dist"]):.1f} {y.dunit}',
                                     'date': a['_day'].strftime('%b %d').replace(' 0', ' ')} for a in top]}))

    # 4. go-to route
    cl = y.route_clusters()
    if cl and len(cl[0]['acts']) >= 4:
        c = cl[0]
        rep = c['acts'][len(c['acts']) // 2]
        route = None
        for a in c['acts']:
            p = os.path.join(y.dir, 'routes', f'{a.get("id")}.json')
            if os.path.exists(p):
                route = load(y.dir, os.path.join('routes', f'{a.get("id")}.json'), None)
                break
        if route and len(route) > 10:
            C.append((88, {'module': 'route', 'key': 'route', 'kicker': f'{fam_name(c["fam"])} · most repeated route',
                           'headline': 'My go-to route', 'points': trim_route(route),
                           'count': len(c['acts']),
                           'body': f'{len(c["acts"])}× this {y.km(c["dist"]):.1f} {y.dunit} loop'
                                   if hav(route[0], route[-1]) < 300 else f'{len(c["acts"])}× this {y.km(c["dist"]):.1f} {y.dunit} route',
                           '_route_id': rep.get('id')}))
        else:
            C.append((0, {'module': '_need_route', 'activity_ids': [a.get('id') for a in c['acts'][:3]]}))

    # 5. calendar
    days = y.active_days()
    if len(days) >= 15:
        months = Counter(x.month for x in days)
        bm = max(months, key=months.get)
        C.append((72, {'module': 'calendar', 'key': 'calendar', 'kicker': y.period, 'headline': f'{len(days)} active days',
                       'active': [x.isoformat() for x in days], 'start': y.start.isoformat(), 'end': y.end.isoformat(),
                       'body': f'Longest streak: {y.streak()} days in a row. Busiest month: {MONTHS[bm - 1]}.'}))

    # 6. power hour
    hours = [int(str(a.get('start_local'))[11:13]) for a in y.acts if a.get('start_local') and len(str(a.get('start_local'))) >= 13]
    if len(hours) >= 15:
        hc = Counter(hours)
        h0 = max(hc, key=hc.get)
        share = sum(v for h, v in hc.items() if h < 10) / len(hours)
        label = f'{(h0 % 12) or 12} {"AM" if h0 < 12 else "PM"}'
        body = (f'{share:.0%} of my workouts started before 10 AM.' if share >= 0.5 else
                f'{1 - share:.0%} of my workouts started after 10 AM.')
        C.append((58, {'module': 'clock', 'key': 'clock', 'kicker': 'When I train', 'headline': 'My power hour',
                       'hours': [hc.get(h, 0) for h in range(24)], 'peak': h0, 'label': label, 'body': body}))

    # 7. VO2max trend
    if len(y.vo2) >= 4:
        v = [num(x['value']) for x in y.vo2]
        delta = v[-1] - v[0]
        sc = 84 if abs(delta) >= 1 else 45
        first_m, last_m = MONTHS[d(y.vo2[0]['date']).month - 1], MONTHS[d(y.vo2[-1]['date']).month - 1]
        C.append((sc, {'module': 'trend', 'key': 'vo2max', 'kicker': 'VO2 max', 'headline': 'VO2 max went up' if delta > 0 else 'VO2 max this year',
                       'delta': big(delta, 1, '+' if delta > 0 else ''), 'series': [[x['date'], num(x['value'])] for x in y.vo2],
                       'start_label': f'{v[0]:.1f}', 'end_label': f'{v[-1]:.1f}', 'peak': round(max(v), 1),
                       'body': f'From {v[0]:.1f} in {first_m} to {v[-1]:.1f} in {last_m}.' + (f' Peak: {max(v):.1f}.' if max(v) - v[-1] >= 0.3 else '')}))

    # 8. fitness age
    fa, age = num(y.prof.get('fitness_age')), num(y.prof.get('age'))
    if fa and age and abs(age - fa) >= 1:
        diff = age - fa
        C.append((70 if diff > 0 else 35, {'module': 'versus', 'key': 'fitness_age', 'kicker': 'Fitness age', 'headline': 'Younger on the inside' if diff > 0 else 'Fitness age',
                                           'left': {'value': int(round(age)), 'label': 'real age'},
                                           'right': {'value': int(round(fa)), 'label': 'fitness age'},
                                           'body': f'My body acts {abs(diff):.0f} {plural(abs(diff), "year")} {"younger" if diff > 0 else "older"} than my passport says.'}))

    # 9. sleep
    sl = [x for x in y.sleep if num(x.get('duration_s'))]
    if len(sl) >= 20:
        tot_h = sum(num(x['duration_s']) for x in sl) / 3600
        scores = [(num(x.get('score')), x) for x in sl if num(x.get('score'))]
        stats = [[f'{tot_h / len(sl):.1f} h', 'average night']]
        body = f'That is {tot_h / 24:,.0f} full days asleep.'
        if scores:
            best, bx = max(scores, key=lambda s: s[0])
            stats.append([f'{sum(s for s, _ in scores) / len(scores):.0f}', 'avg sleep score'])
            stats.append([f'{best:.0f}', f'best · {d(bx["date"]).strftime("%b %d").replace(" 0", " ")}'])
        C.append((74, {'module': 'big_number', 'key': 'sleep', 'kicker': f'Sleep · {len(sl)} nights', 'headline': 'I slept',
                       'number': big(tot_h), 'unit': 'hours', 'body': body, 'stats': stats}))

    # 10. steps
    st = [(num(x.get('steps')), x) for x in y.daily if num(x.get('steps'))]
    if len(st) >= 20:
        tot = sum(s for s, _ in st)
        best, bx = max(st, key=lambda s: s[0])
        C.append((68, {'module': 'big_number', 'key': 'steps', 'kicker': f'Steps · {y.period}', 'headline': 'I took',
                       'number': big(tot), 'unit': 'steps',
                       'body': f'About {tot * 0.75 / 1000:,.0f} km on foot, just by living.' if not y.imperial else f'About {tot * 0.75 / 1609.344:,.0f} miles on foot, just by living.',
                       'stats': [[fmt_int(tot / len(st)), 'per day'], [fmt_int(best), f'best · {d(bx["date"]).strftime("%b %d").replace(" 0", " ")}'],
                                 [fmt_int(sum(1 for s, x in st if num(x.get('steps_goal')) and s >= num(x.get('steps_goal')))), 'goals hit']]}))
        C[-1][1]['stats'] = [s for s in C[-1][1]['stats'] if not (s[1] == 'goals hit' and s[0] == '0')]

    # 11. floors
    fl = [num(x.get('floors')) for x in y.daily if num(x.get('floors'))]
    if len(fl) >= 20 and sum(fl) > 300:
        tot = sum(fl)
        C.append((40, {'module': 'big_number', 'key': 'floors', 'kicker': 'Floors climbed', 'headline': 'I climbed',
                       'number': big(tot), 'unit': 'floors', 'body': f'That is the Eiffel Tower {tot * 3 / 330:.0f} times.',
                       'tri_count': min(int(tot * 3 // 330), 40) or None}))

    # 12. HR zones
    z = [0.0] * 5
    for a in y.acts:
        for i, v in enumerate((a.get('hr_zone_s') or [])[:5]):
            z[i] += num(v) or 0
    if sum(z) > 5 * 3600:
        zh = [round(v / 3600, 1) for v in z]
        top = max(range(5), key=lambda i: zh[i])
        C.append((52 if top == 1 else 46, {'module': 'zones', 'key': 'zones', 'kicker': 'Heart rate zones', 'headline': f'{zh[1]:,.0f} hours in zone 2' if top == 1 else f'Mostly zone {top + 1}',
                                           'zones': zh, 'body': 'Easy miles build the engine.' if top <= 1 else 'I like it spicy.'}))

    # 13. resting heart rate
    rhr = [(num(x.get('rhr')), x) for x in y.daily if num(x.get('rhr'))]
    if len(rhr) >= 60:
        low, lx = min(rhr, key=lambda r: r[0])
        series = monthly([(x['date'], r) for r, x in rhr])
        if len(series) >= 3:
            C.append((44, {'module': 'trend', 'key': 'rhr', 'kicker': 'Resting heart rate', 'headline': 'Calmest heart',
                           'delta': big(low, 0, '', ' bpm'), 'series': series, 'start_label': f'{series[0][1]:.0f}', 'end_label': f'{series[-1][1]:.0f}',
                           'peak': None, 'invert': True,
                           'body': f'Lowest: {low:.0f} bpm on {d(lx["date"]).strftime("%b %d").replace(" 0", " ")}.'}))

    # fallbacks so there are always enough slides
    if sessions:
        C.append((20, {'module': 'big_number', 'key': 'sessions', 'kicker': y.period, 'headline': 'I showed up',
                       'number': big(sessions), 'unit': 'workouts', 'body': f'{total_h:,.0f} hours of movement in total.',
                       'tri_count': min(sessions, 40)}))
    kcal = sum(num(x.get('active_kcal')) or 0 for x in y.daily)
    if kcal > 1000:
        C.append((18, {'module': 'big_number', 'key': 'kcal', 'kicker': 'Active calories', 'headline': 'I burned',
                       'number': big(kcal), 'unit': 'kcal', 'body': f'That is roughly {kcal / 285:,.0f} slices of pizza.'}))
    im = sum((num(x.get('intensity_min')) or 0) for x in y.daily)
    if im > 300:
        C.append((16, {'module': 'big_number', 'key': 'intensity', 'kicker': 'Intensity minutes', 'headline': 'I earned',
                       'number': big(im), 'unit': 'intensity minutes', 'body': f'The WHO asks for 150 a week. I averaged {im / max(1, (y.end - y.start).days / 7):,.0f}.'}))
    return C


def monthly(pairs):
    by = defaultdict(list)
    for date, v in pairs:
        by[str(date)[:7]].append(v)
    return [[k + '-15', round(sum(v) / len(v), 1)] for k, v in sorted(by.items())]


def trim_route(pts, cut_m=200):
    """Privacy: drop the first and last ~200 m so nobody can find a front door. Then thin to <= 400 points."""
    pts = [(float(p[0]), float(p[1])) for p in pts if p and p[0] is not None]
    def cut(seq):
        acc = 0
        for i in range(1, len(seq)):
            acc += hav(seq[i - 1], seq[i])
            if acc >= cut_m:
                return seq[i:]
        return seq
    if len(pts) > 20:
        pts = cut(pts)
        pts = cut(pts[::-1])[::-1]
    step = max(1, len(pts) // 400)
    return [[round(a, 6), round(b, 6)] for a, b in pts[::step]]


def persona(y):
    fams = y.families()
    total_h = sum(g['hours'] for _, g in fams) or 1
    hours = [int(str(a.get('start_local'))[11:13]) for a in y.acts if a.get('start_local') and len(str(a.get('start_local'))) >= 13]
    early = sum(1 for h in hours if h < 9) / max(1, len(hours))
    late = sum(1 for h in hours if h >= 18) / max(1, len(hours))
    weekend = sum(1 for a in y.acts if a['_day'].weekday() >= 5) / max(1, len(y.acts))
    top_share = fams[0][1]['hours'] / total_h if fams else 0
    zones = [0.0] * 5
    for a in y.acts:
        for i, v in enumerate((a.get('hr_zone_s') or [])[:5]):
            zones[i] += num(v) or 0
    easy = (zones[0] + zones[1]) / max(1, sum(zones))
    days = len(y.active_days())
    span = max(1, (y.end - y.start).days + 1)
    traits = []
    if early >= 0.45:
        name, desc = 'The Early Bird', 'Most of my training happens before the world wakes up.'
    elif late >= 0.45:
        name, desc = 'The Night Owl', 'When the day is done, my training starts.'
    elif len([f for f, g in fams if g['hours'] / total_h >= 0.15]) >= 3:
        name, desc = 'The Hybrid Athlete', 'I refuse to pick just one sport.'
    elif days / span >= 0.55:
        name, desc = 'The Streak Machine', 'I show up. Then I show up again.'
    elif weekend >= 0.5:
        name, desc = 'The Weekend Warrior', 'Weekdays are for work. Weekends are for this.'
    elif sum(zones) and easy >= 0.7:
        name, desc = 'The Base Builder', 'Slow and steady. The engine keeps growing.'
    elif top_share >= 0.7 and fams:
        name, desc = f'The {fam_name(fams[0][0])} Purist', f'{top_share:.0%} of my training was {fam_name(fams[0][0]).lower()}.'
    else:
        name, desc = 'The All-Rounder', 'A bit of everything, all year long.'
    if fams:
        traits.append(f'{top_share:.0%} {fam_name(fams[0][0]).lower()}')
    traits.append(f'{days} active days')
    if hours:
        traits.append(f'{early:.0%} before 9 AM' if early >= late else f'{late:.0%} after 6 PM')
    return {'module': 'persona', 'key': 'persona', 'kicker': 'My 2026 training personality'.replace('2026', str(y.year)),
            'name': name, 'body': desc, 'traits': traits[:3]}


ORDER = ['podium', 'hero_', 'records', 'route', 'calendar', 'clock', 'vo2max', 'zones', 'fitness_age', 'rhr', 'sleep', 'steps', 'floors', 'sessions', 'kcal', 'intensity']


def order_key(s):
    k = s['key']
    for i, o in enumerate(ORDER):
        if k.startswith(o):
            return i
    return len(ORDER)


def plan(y):
    cands = build_candidates(y)
    need = [s for _, s in cands if s['module'] == '_need_route']
    cands = sorted([c for c in cands if c[1]['module'] != '_need_route'], key=lambda c: -c[0])
    chosen, big_n = [], 0
    for score, s in cands:
        if len(chosen) == 7:
            break
        if s['module'] == 'big_number' and big_n >= 3 and not s['key'].startswith('hero_'):
            continue
        chosen.append(s)
        big_n += s['module'] == 'big_number'
    for score, s in cands:  # fill if strict rules left gaps
        if len(chosen) == 7:
            break
        if s not in chosen:
            chosen.append(s)
    chosen.sort(key=order_key)
    fams = y.families()
    total_h = sum(g['hours'] for _, g in fams)
    steps = sum(num(x.get('steps')) or 0 for x in y.daily)
    if total_h >= 5:
        hook = {'number': big(total_h), 'unit': 'hours of training'}
    elif steps:
        hook = {'number': big(steps), 'unit': 'steps'}
    else:
        hook = {'number': big(len(y.acts)), 'unit': 'workouts'}
    intro = {'module': 'intro', 'key': 'intro', 'kicker': (f"{y.name}'s year on the wrist" if y.name else 'My year on the wrist'),
             'title': ['Garmin', f"Wrapped '{str(y.year)[2:]}"], 'hook': hook, 'period': y.period,
             'footer': ['Swipe through my year', f'Garmin data · {y.period}']}
    cta = {'module': 'cta', 'key': 'cta', 'title': ['Make your own', 'Garmin Wrapped'],
           'body': 'Free prompt from the Garmin School',
           'handles': [['Instagram', '@vawbe'], ['TikTok', '@vaw.be'], ['YouTube', '@vawbe']], 'site': 'garmin.vaw.be'}
    slides = [intro] + chosen[:7] + [persona(y), cta]
    while len(slides) < 10:  # extremely thin data: repeat-safe generic slide
        slides.insert(-2, {'module': 'big_number', 'key': f'pad{len(slides)}', 'kicker': y.period, 'headline': 'Still counting',
                           'number': big(len(y.active_days())), 'unit': 'active days', 'body': 'Every day on the wrist counts.'})
    return {'meta': {'name': y.name, 'year': y.year, 'period': y.period, 'units': 'imperial' if y.imperial else 'metric',
                     'generated': dt.datetime.now().isoformat(timespec='seconds')},
            'slides': slides, 'routes_to_fetch': need[0]['activity_ids'] if need else []}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    y = Year(sys.argv[1])
    p = plan(y)
    if '--plan' in sys.argv:
        print(json.dumps({'routes_to_fetch': p['routes_to_fetch']}))
        return
    out = os.path.join(sys.argv[1], 'wrapped.json')
    with open(out, 'w') as fh:
        json.dump(p, fh, indent=1)
    print(f'{len(y.acts)} activities, {len(y.daily)} days, {len(y.sleep)} nights, {len(y.vo2)} VO2 max points  ({y.period})')
    for i, s in enumerate(p['slides'], 1):
        print(f'{i:2d}. {s["module"]:<10} {s.get("key", "")}')
    if p['routes_to_fetch']:
        print('TIP: fetch a GPS polyline for one of these activity ids into routes/<id>.json to unlock the route slide:', p['routes_to_fetch'])
    print('wrote', out)


if __name__ == '__main__':
    main()
