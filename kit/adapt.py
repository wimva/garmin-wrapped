#!/usr/bin/env python3
"""Garmin Wrapped '26 — step 1b: turn whatever a Garmin connector returned into the kit's data format.

    python adapt.py RAW_DIR DATA_DIR

Different Garmin MCP connectors return the same Garmin data with different field names and shapes:
camelCase Garmin Connect fields (`activityId`, `startTimeLocal`, `sleepScores.overall.value`) or snake_case
connector fields (`id`, `start_time`, `duration_seconds`, `sleep_score`), epoch milliseconds or ISO strings,
plain lists or paged objects (`{"activities": [...]}`, `{"data": [...], "next": ...}`). This adapter accepts
all of them and writes only the fields in SCHEMA.md — everything else (names, devices, GPS other than the
start point and requested routes, notes…) is dropped.

RAW_DIR layout (save every tool result as it came, one file per call/page; any *.json name):

    raw/profile.json                  first_name, year, end_date, units, age, fitness_age, timezone (any naming)
    raw/activities/*.json             activity lists, any number of pages
    raw/daily/*.json                  daily summaries
    raw/sleep/*.json                  sleep nights
    raw/vo2max/*.json                 VO2 max history
    raw/hrv/*.json                    HRV history
    raw/routes/<activity_id>.json     GPS polyline of one activity (only when compute.py asks)

Also importable: compute.py runs every record through these normalizers, so already-normalized data passes
through unchanged. Pure Python 3 standard library.
"""
import datetime as dt
import glob
import json
import math
import os
import re
import sys

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None


# ============================================================================================ generic access
def nk(k):
    """Normalized key: 'startTimeLocal', 'start_time_local' and 'Start-Time-Local' all become 'starttimelocal'."""
    return re.sub(r'[^a-z0-9]', '', str(k).lower())


def get(rec, *paths):
    """First non-empty value found under any of the dotted paths (path segments in normalized form)."""
    for path in paths:
        cur = rec
        for seg in path.split('.'):
            if isinstance(cur, dict):
                nxt = None
                for k, v in cur.items():
                    if nk(k) == seg:
                        nxt = v
                        break
                cur = nxt
            else:
                cur = None
            if cur is None:
                break
        if cur not in (None, '', [], {}):
            return cur
    return None


def num(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def records(obj):
    """Flatten a tool result into a list of record dicts: plain lists, paged objects, nested 'data' wrappers."""
    if isinstance(obj, list):
        out = []
        for x in obj:
            if isinstance(x, dict):
                inner = records_in(x)
                out.extend(inner if inner is not None else [x])
        return out
    if isinstance(obj, dict):
        inner = records_in(obj)
        return inner if inner is not None else [obj]
    return []


def records_in(d):
    """If d is a wrapper ({"activities": [...], "next": ...}), return its records; else None (d is a record)."""
    lists = [v for v in d.values() if isinstance(v, list) and v and all(isinstance(x, dict) for x in v)]
    looks_like_record = any(nk(k) in RECORD_HINTS for k in d)
    if lists and not looks_like_record:
        out = []
        for v in lists:
            out.extend(records(v))
        return out
    for k in ('data', 'result', 'results', 'payload'):
        v = get(d, k)
        if isinstance(v, (dict, list)) and not looks_like_record:
            return records(v)
    return None


RECORD_HINTS = {'activityid', 'id', 'calendardate', 'date', 'starttimelocal', 'starttime', 'sleeptimeseconds',
                'sleepseconds', 'vo2max', 'vo2maxvalue', 'lastnightavg', 'day'}


# ============================================================================================ time
class Clock:
    """Converts epoch numbers and ISO strings to local wall-clock time (profile timezone if known)."""

    def __init__(self, tz=None, offset_h=None):
        self.tz = None
        if tz and ZoneInfo:
            try:
                self.tz = ZoneInfo(str(tz))
            except Exception:
                self.tz = None
        self.offset = dt.timedelta(hours=float(offset_h)) if num(offset_h) is not None else None

    def to_local(self, aware):
        if self.tz:
            return aware.astimezone(self.tz).replace(tzinfo=None)
        if self.offset is not None:
            return (aware.astimezone(dt.timezone.utc) + self.offset).replace(tzinfo=None)
        return aware.astimezone(dt.timezone.utc).replace(tzinfo=None)

    def parse(self, v, local=False):
        """local=True: the value already is local wall time (e.g. Garmin's *TimestampLocal / startTimeLocal)."""
        if v is None or v == '':
            return None
        x = num(v) if not isinstance(v, str) or re.fullmatch(r'\d{9,}(\.\d+)?', v.strip()) else None
        if x is not None:
            if x > 1e11:      # epoch milliseconds
                x /= 1000.0
            if x < 1e8:       # not an epoch
                return None
            if local:
                return dt.datetime(1970, 1, 1) + dt.timedelta(seconds=x)
            return self.to_local(dt.datetime.fromtimestamp(x, dt.timezone.utc))
        s = str(v).strip().replace(' ', 'T')
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', s):
            return dt.datetime.fromisoformat(s)
        s = s.replace('Z', '+00:00')
        s = re.sub(r'\.(\d{1,6})\d*', r'.\1', s)
        try:
            t = dt.datetime.fromisoformat(s)
        except ValueError:
            return None
        if t.tzinfo is not None and not local:
            return self.to_local(t)
        return t.replace(tzinfo=None)


def iso(t):
    return t.strftime('%Y-%m-%dT%H:%M:%S') if t else None


def day(t):
    return t.strftime('%Y-%m-%d') if t else None


# ============================================================================================ units
def seconds(rec, paths_s, paths_ms=(), paths_min=()):
    for p in paths_s:
        v = num(get(rec, p))
        if v is not None:
            return v
    for p in paths_ms:
        v = num(get(rec, p))
        if v is not None:
            return v / 1000.0
    for p in paths_min:
        v = num(get(rec, p))
        if v is not None:
            return v * 60.0
    return None


def metres(rec, paths_m, paths_km=(), paths_mi=()):
    for p in paths_m:
        v = num(get(rec, p))
        if v is not None:
            return v
    for p in paths_km:
        v = num(get(rec, p))
        if v is not None:
            return v * 1000.0
    for p in paths_mi:
        v = num(get(rec, p))
        if v is not None:
            return v * 1609.344
    return None


def clean(d):
    return {k: v for k, v in d.items() if v is not None}


# ============================================================================================ normalizers
def norm_sport(v):
    if isinstance(v, dict):
        v = get(v, 'typekey', 'key', 'name', 'type')
    if v is None:
        return None
    return re.sub(r'[^a-z0-9]+', '_', str(v).strip().lower()).strip('_') or None


SPLITS = [('fastest_1k_s', ['fastest1ks', 'fastestsplit1000', 'fastestsplit1k', 'fastest1000', 'fastest1k']),
          ('fastest_mile_s', ['fastestmiles', 'fastestsplit1609', 'fastestmile', 'fastest1609']),
          ('fastest_5k_s', ['fastest5ks', 'fastestsplit5000', 'fastestsplit5k', 'fastest5000', 'fastest5k']),
          ('fastest_10k_s', ['fastest10ks', 'fastestsplit10000', 'fastestsplit10k', 'fastest10000', 'fastest10k']),
          ('fastest_half_s', ['fastesthalfs', 'fastestsplit21098', 'fastestsplit21097', 'fastesthalfmarathon', 'fastesthalf']),
          ('fastest_marathon_s', ['fastestmarathons', 'fastestsplit42195', 'fastestmarathon'])]


def norm_activity(r, clock):
    local = get(r, 'starttimelocal', 'startlocal', 'localstarttime', 'starttimelocalstr')
    t = clock.parse(local, local=True) if local is not None else None
    if t is None:
        g = get(r, 'starttime', 'starttimegmt', 'starttimeutc', 'start', 'begintimestamp', 'starttimestamp', 'date')
        t = clock.parse(g, local=False)
    zones = get(r, 'hrzones', 'hrzonesecs')
    if not isinstance(zones, list) or len(zones) < 5:
        zones = [num(get(r, f'hrtimeinzone{i}', f'timeinzone{i}', f'hrzone{i}', f'zone{i}seconds')) for i in range(1, 6)]
    zones = [round(z, 1) if z is not None else 0.0 for z in zones[:5]] if any(z for z in zones[:5] if z) else None
    out = {
        'id': get(r, 'activityid', 'id', 'activityuuid'),
        'date': day(t) if t else (str(get(r, 'date'))[:10] if get(r, 'date') else None),
        'start_local': iso(t),
        'sport': norm_sport(get(r, 'activitytype.typekey', 'activitytype', 'type', 'sport', 'sporttype', 'activitytypekey', 'typekey')),
        'duration_s': seconds(r, ['durations', 'duration', 'durationseconds', 'durationinseconds', 'elapseddurationseconds',
                                  'elapsedduration', 'movingduration', 'totaltimeseconds', 'timeseconds'],
                              ['durationms', 'durationmillis', 'durationinmillis'], ['durationminutes', 'durationmin']),
        'distance_m': metres(r, ['distancem', 'distance', 'distancemeters', 'distanceinmeters', 'totaldistance', 'totaldistancemeters'],
                             ['distancekm', 'distancekilometers', 'distanceinkm'], ['distancemiles', 'distancemi']),
        'elevation_gain_m': metres(r, ['elevationgainm', 'elevationgain', 'elevationgainmeters', 'totalascent', 'ascent', 'elevationgaininmeters'],
                                   [], []),
        'avg_hr': num(get(r, 'avghr', 'averagehr', 'avghrbpm', 'averageheartrate', 'averageheartratebpm', 'avgheartrate')),
        'calories': num(get(r, 'calories', 'caloriesKcal'.lower(), 'activecalories', 'kilocalories', 'activekilocalories')),
        'hr_zone_s': zones,
        'start_lat': None, 'start_lon': None,
        'reps': num(get(r, 'reps', 'totalreps')),
        'sets': num(get(r, 'sets', 'totalsets', 'activesets')),
        'volume_kg': num(get(r, 'volumekg', 'totalvolume', 'volume')),
    }
    for field, keys in SPLITS:
        out[field] = num(get(r, *keys))
    lat = num(get(r, 'startlat', 'startlatitude', 'startposition.lat', 'startposition.latitude', 'latitude'))
    lon = num(get(r, 'startlon', 'startlongitude', 'startposition.lon', 'startposition.longitude', 'longitude'))
    if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180 and not (lat == 0 and lon == 0):
        out['start_lat'], out['start_lon'] = round(lat, 4), round(lon, 4)   # only used to group repeated routes, never shown
    if out['volume_kg'] is None:
        sets = get(r, 'summarizedexercisesets')
        if isinstance(sets, list):
            vol = sum(num(get(s, 'volume')) or 0 for s in sets if isinstance(s, dict))
            out['volume_kg'] = vol / 1000.0 if vol > 100000 else (vol or None)   # Garmin reports grams in some versions
    return clean(out)


def norm_daily(r, clock):
    d = get(r, 'calendardate', 'date', 'day', 'summarydate')
    t = clock.parse(d, local=True) if d is not None else None
    mod = num(get(r, 'moderateintensityminutes', 'intensityminutes.moderate', 'moderateminutes', 'intensityminutesmoderate'))
    vig = num(get(r, 'vigorousintensityminutes', 'intensityminutes.vigorous', 'vigorousminutes', 'intensityminutesvigorous'))
    im = num(get(r, 'intensitymin', 'intensityminutestotal', 'intensityminutes'))
    if mod is not None or vig is not None:
        im = (mod or 0) + 2 * (vig or 0)
    return clean({
        'date': day(t),
        'steps': num(get(r, 'steps', 'totalsteps', 'movement.steps.value', 'stepcount', 'dailysteps')),
        'steps_goal': num(get(r, 'stepsgoal', 'dailystepgoal', 'movement.steps.goal', 'stepgoal')),
        'floors': num(get(r, 'floors', 'floorsascended', 'movement.floorsascended.value', 'floorsclimbed')),
        'rhr': num(get(r, 'rhr', 'restingheartrate', 'heartrate.restingvalue', 'restinghr', 'restinghrbpm', 'restingheartratebpm')),
        'intensity_min': im,
        'active_kcal': num(get(r, 'activekcal', 'activekilocalories', 'calories.burnedactive', 'activecalories', 'caloriesactive')),
    })


def norm_sleep(r, clock):
    r = get(r, 'dailysleepdto') if isinstance(get(r, 'dailysleepdto'), dict) else r
    d = get(r, 'calendardate', 'date', 'day', 'sleepdate')
    t = clock.parse(d, local=True) if d is not None else None
    start = None
    if get(r, 'sleepstarttimestamplocal', 'startlocal', 'sleepstartlocal') is not None:
        start = clock.parse(get(r, 'sleepstarttimestamplocal', 'startlocal', 'sleepstartlocal'), local=True)
    elif get(r, 'sleepstart', 'sleepstarttimestampgmt', 'starttime', 'sleepstarttime', 'bedtime') is not None:
        start = clock.parse(get(r, 'sleepstart', 'sleepstarttimestampgmt', 'starttime', 'sleepstarttime', 'bedtime'), local=False)
    score = get(r, 'score', 'sleepscore', 'sleepscores.overall.value', 'overallscore', 'sleepscore.value', 'sleepscores.overall')
    if isinstance(score, dict):
        score = get(score, 'value', 'overall.value')
    dur = seconds(r, ['durations', 'sleeptimeseconds', 'sleepseconds', 'totalsleepseconds', 'sleepdurationseconds', 'durationseconds'],
                  ['sleeptimemillis', 'sleepdurationms'], ['sleepminutes', 'totalsleepminutes', 'sleepdurationminutes'])
    return clean({'date': day(t), 'duration_s': dur if dur and dur > 0 else None,
                  'score': num(score) if num(score) and num(score) > 0 else None, 'start_local': iso(start)})


def norm_point(r, clock, keys):
    """VO2 max / HRV: one real measurement per date. Missing or zero values are skipped, never stored as 0."""
    if get(r, 'carriedforward', 'iscarriedforward', 'carryforward') in (True, 'true', 'True', 1):
        return None   # a repeated historical value, not a new measurement
    d = get(r, 'calendardate', 'date', 'day', 'generic.calendardate')
    t = clock.parse(d, local=True) if d is not None else None
    v = num(get(r, *keys))
    if not t or v is None or v <= 0:
        return None
    return {'date': day(t), 'value': round(v, 1)}


VO2_KEYS = ['value', 'vo2maxprecisevalue', 'generic.vo2maxprecisevalue', 'vo2max', 'vo2maxvalue', 'generic.vo2maxvalue',
            'vo2maxrunning', 'cycling.vo2maxprecisevalue']
HRV_KEYS = ['value', 'lastnightavg', 'hrvsummary.lastnightavg', 'nightlyavg', 'nightlyhrv', 'avghrv', 'hrv', 'lastnightaverage',
            'hrvlastnightavg', 'rmssd']


def norm_profile(r):
    p = {
        'first_name': get(r, 'firstname', 'givenname', 'name'),
        'year': num(get(r, 'year')),
        'end_date': get(r, 'enddate'),
        'units': get(r, 'units', 'measurementsystem', 'unitsystem'),
        'age': num(get(r, 'age', 'chronologicalage')),
        'fitness_age': num(get(r, 'fitnessage')),
        'timezone': get(r, 'timezone', 'tz', 'timezoneid'),
        'utc_offset_hours': num(get(r, 'utcoffsethours', 'utcoffset')),
    }
    if p['first_name']:
        p['first_name'] = str(p['first_name']).split()[0]      # first name only
    if p['units']:
        p['units'] = 'imperial' if 'imp' in str(p['units']).lower() or 'statute' in str(p['units']).lower() else 'metric'
    if p['year']:
        p['year'] = int(p['year'])
    for k in ('age', 'fitness_age'):
        if p[k]:
            p[k] = round(p[k], 1)
    return clean(p)


def norm_route(obj):
    """GPS polyline in any shape → [[lat, lon], ...]. Invalid points are dropped (compute.py trims and anonymizes)."""
    pts = get(obj, 'geopolylinedto.polyline', 'polyline', 'points', 'coordinates', 'route', 'path') if isinstance(obj, dict) else obj
    out = []
    for p in pts or []:
        if isinstance(p, dict):
            lat, lon = num(get(p, 'lat', 'latitude')), num(get(p, 'lon', 'lng', 'longitude'))
        elif isinstance(p, (list, tuple)) and len(p) >= 2:
            lat, lon = num(p[0]), num(p[1])
        else:
            continue
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
            continue
        out.append([round(lat, 6), round(lon, 6)])
    return out


# ============================================================================================ files
def load_json(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def read_all(path):
    out = []
    files = sorted(glob.glob(os.path.join(path, '*.json'))) if os.path.isdir(path) else ([path] if os.path.exists(path) else [])
    for f in files:
        try:
            out.extend(records(load_json(f)))
        except Exception as e:
            print(f'skipped {f}: {e}', file=sys.stderr)
    return out


def dedupe(rows, key):
    seen, out = set(), []
    for r in rows:
        k = key(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def adapt(raw, data):
    os.makedirs(data, exist_ok=True)
    prof_raw = {}
    pp = os.path.join(raw, 'profile.json')
    if os.path.exists(pp):
        obj = load_json(pp)
        prof_raw = obj if isinstance(obj, dict) else (obj[0] if obj else {})
    prof = norm_profile(prof_raw)
    clock = Clock(prof.get('timezone'), prof.get('utc_offset_hours'))
    acts = [norm_activity(r, clock) for r in read_all(os.path.join(raw, 'activities'))]
    acts = dedupe([a for a in acts if a.get('date') and (a.get('duration_s') or a.get('distance_m'))],
                  lambda a: a.get('id') or (a.get('start_local'), a.get('sport')))
    daily = dedupe([x for x in (norm_daily(r, clock) for r in read_all(os.path.join(raw, 'daily'))) if x.get('date')], lambda x: x['date'])
    sleep = dedupe([x for x in (norm_sleep(r, clock) for r in read_all(os.path.join(raw, 'sleep'))) if x.get('date') and x.get('duration_s')],
                   lambda x: x['date'])
    vo2 = dedupe([x for x in (norm_point(r, clock, VO2_KEYS) for r in read_all(os.path.join(raw, 'vo2max'))) if x], lambda x: x['date'])
    hrv = dedupe([x for x in (norm_point(r, clock, HRV_KEYS) for r in read_all(os.path.join(raw, 'hrv'))) if x], lambda x: x['date'])
    out = {'profile': prof, 'activities': sorted(acts, key=lambda a: a.get('start_local') or a['date']),
           'daily': sorted(daily, key=lambda x: x['date']), 'sleep': sorted(sleep, key=lambda x: x['date']),
           'vo2max': sorted(vo2, key=lambda x: x['date']), 'hrv': sorted(hrv, key=lambda x: x['date'])}
    for name, obj in out.items():
        with open(os.path.join(data, f'{name}.json'), 'w', encoding='utf-8') as fh:
            json.dump(obj, fh, separators=(',', ':'))
    rdir = os.path.join(raw, 'routes')
    if os.path.isdir(rdir):
        os.makedirs(os.path.join(data, 'routes'), exist_ok=True)
        for f in glob.glob(os.path.join(rdir, '*.json')):
            pts = norm_route(load_json(f))
            if pts:
                with open(os.path.join(data, 'routes', os.path.basename(f)), 'w') as fh:
                    json.dump(pts, fh)
    print(f"adapted: {len(acts)} activities, {len(daily)} days, {len(sleep)} nights, {len(vo2)} VO2 max, {len(hrv)} HRV"
          f"{', timezone ' + prof['timezone'] if prof.get('timezone') else ''} → {data}")
    return out


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    adapt(sys.argv[1], sys.argv[2])
