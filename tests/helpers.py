import json, math, os, sys, tempfile, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'kit'))

CENTER = (50.8466, 4.3528)


def loop(km=5.0, n=200, center=CENTER):
    R = km * 1000 / (2 * math.pi)
    return [[center[0] + R * math.sin(2 * math.pi * i / n) / 111320,
             center[1] + R * math.cos(2 * math.pi * i / n) / (111320 * math.cos(math.radians(center[0])))] for i in range(n + 1)]


def line(km=3.0, n=100, start=CENTER):
    return [[start[0] + km * 1000 * i / n / 111320, start[1]] for i in range(n + 1)]


def write(d, name, obj):
    os.makedirs(os.path.dirname(os.path.join(d, name)) or d, exist_ok=True)
    with open(os.path.join(d, name), 'w') as fh:
        json.dump(obj, fh)


def tmpdir():
    return tempfile.mkdtemp(prefix='gw_test_')


def runner_data(d, route=None, hrv=None, n_runs=12):
    """Minimal runner dataset with a repeated route; optional route polyline and HRV list."""
    acts = []
    for k in range(n_runs):
        day = dt.date(2026, 1, 5) + dt.timedelta(days=7 * k)
        acts.append({'id': 100 + k, 'date': day.isoformat(), 'start_local': f'{day}T08:00:00', 'sport': 'running',
                     'duration_s': 1800, 'distance_m': 5000, 'start_lat': CENTER[0], 'start_lon': CENTER[1]})
    write(d, 'activities.json', acts)
    write(d, 'profile.json', {'year': 2026, 'end_date': '2026-11-20'})
    if route is not None:
        write(d, 'routes/100.json', route)
    if hrv is not None:
        write(d, 'hrv.json', hrv)
