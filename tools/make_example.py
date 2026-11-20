"""Generate a realistic but FAKE example dataset (example/data) to test the kit without a Garmin account.
    python tools/make_example.py [runner|cyclist|lifter]
"""
import json, math, os, random, sys, datetime as dt

kind = sys.argv[1] if len(sys.argv) > 1 else 'runner'
random.seed({'runner': 7, 'cyclist': 11, 'lifter': 5}[kind])
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'example', kind)
os.makedirs(os.path.join(OUT, 'routes'), exist_ok=True)
start, end = dt.date(2026, 1, 1), dt.date(2026, 11, 20)
days = [(start + dt.timedelta(n)) for n in range((end - start).days + 1)]
HOME = (50.8466, 4.3528)  # fictional start point (central Brussels), not anyone's home


def loop(center, km, n=180, seed=1):
    r = random.Random(seed)
    R = km * 1000 / (2 * math.pi)
    ph = [r.random() * 6.28 for _ in range(4)]
    pts = []
    for i in range(n + 1):
        a = 2 * math.pi * i / n
        rr = R * (1 + 0.22 * math.sin(2 * a + ph[0]) + 0.12 * math.sin(3 * a + ph[1]) + 0.06 * math.sin(5 * a + ph[2]))
        dx, dy = rr * math.cos(a) * 1.25, rr * math.sin(a) * 0.8
        pts.append([round(center[0] + dy / 111320, 6), round(center[1] + dx / (111320 * math.cos(math.radians(center[0]))), 6)])
    return pts


acts, aid = [], 1000
plan = {'runner': [('running', 0.52), ('walking', 0.12), ('strength_training', 0.1), ('hiit', 0.05), ('cycling', 0.03)],
        'cyclist': [('road_biking', 0.38), ('indoor_cycling', 0.18), ('running', 0.08), ('strength_training', 0.08), ('hiking', 0.03)],
        'lifter': [('strength_training', 0.55), ('indoor_rowing', 0.12), ('walking', 0.2), ('yoga', 0.08), ('padel', 0.06)]}[kind]
for day in days:
    for sport, p in plan:
        if random.random() > p:
            continue
        aid += 1
        hour = random.choice([7, 7, 8, 8, 8, 12, 18, 19]) if kind == 'runner' else random.choice([6, 9, 10, 17, 18, 19, 20])
        a = {'id': aid, 'date': day.isoformat(), 'start_local': f'{day}T{hour:02d}:{random.randint(0, 59):02d}:00', 'sport': sport}
        prog = (day - start).days / 365
        if sport == 'running':
            regular = random.random() < 0.65
            km = 5.1 if regular else random.choice([3.2, 6.4, 8.0, 10.2, 12.5, 15.0, 21.1])
            pace = 345 - 25 * prog + random.uniform(-15, 25)
            a.update(distance_m=km * 1000 * random.uniform(0.99, 1.01), duration_s=km * pace, elevation_gain_m=km * random.uniform(1, 4),
                     avg_hr=random.randint(132, 156), calories=int(km * 82), fastest_1k_s=pace - random.uniform(10, 30),
                     fastest_mile_s=(pace - random.uniform(8, 25)) * 1.609, start_lat=HOME[0] + random.uniform(-3e-4, 3e-4),
                     start_lon=HOME[1] + random.uniform(-3e-4, 3e-4))
            if km >= 5:
                a['fastest_5k_s'] = 5 * (pace - random.uniform(0, 12))
            if km >= 10:
                a['fastest_10k_s'] = 10 * (pace - random.uniform(-5, 8))
            if km >= 21:
                a['fastest_half_s'] = 21.0975 * (pace + random.uniform(0, 10))
            z = a['duration_s']
            a['hr_zone_s'] = [z * 0.12, z * 0.48, z * 0.28, z * 0.1, z * 0.02]
            if regular and not os.path.exists(os.path.join(OUT, 'routes', f'{aid}.json')) and random.random() < 0.05:
                json.dump(loop(HOME, 5.1, seed=3), open(os.path.join(OUT, 'routes', f'{aid}.json'), 'w'))
        elif sport in ('cycling', 'road_biking'):
            km = random.choice([25, 40, 55, 70, 90, 120])
            a.update(distance_m=km * 1000, duration_s=km / random.uniform(26, 31) * 3600, elevation_gain_m=km * random.uniform(4, 9),
                     avg_hr=random.randint(125, 148), calories=int(km * 28), start_lat=HOME[0] + 0.02, start_lon=HOME[1] - 0.03)
        elif sport == 'indoor_cycling':
            a.update(duration_s=random.choice([2700, 3600, 4500]), distance_m=0, calories=520)
        elif sport in ('walking', 'hiking'):
            km = random.uniform(2.5, 7) if sport == 'walking' else random.uniform(10, 22)
            a.update(distance_m=km * 1000, duration_s=km * 720, elevation_gain_m=km * (3 if sport == 'walking' else 45), calories=int(km * 55))
        elif sport == 'strength_training':
            a.update(duration_s=random.choice([1800, 2700, 3600]), calories=random.randint(180, 380), reps=random.randint(90, 220),
                     sets=random.randint(12, 24), volume_kg=random.randint(2500, 9000))
        elif sport == 'indoor_rowing':
            a.update(duration_s=1800, distance_m=random.randint(5000, 7500), calories=320)
        else:
            a.update(duration_s=random.choice([1200, 1800, 3600]), calories=random.randint(120, 400))
        acts.append(a)

daily, sleep, hrv = [], [], []
for day in days:
    prog = (day - start).days / 365
    daily.append({'date': day.isoformat(), 'steps': int(random.gauss(10400, 2600)), 'steps_goal': 10000, 'floors': random.randint(4, 22),
                  'rhr': round(58 - 5 * prog + random.uniform(-2, 2)), 'intensity_min': random.randint(0, 70), 'active_kcal': random.randint(250, 900)})
    if random.random() < 0.94:
        dur = random.gauss(7.3, 0.6) * 3600
        sleep.append({'date': day.isoformat(), 'duration_s': dur, 'score': min(98, int(random.gauss(76, 9))),
                      'start_local': f'{day}T{random.choice([22, 22, 23, 23, 23, 0])}:{random.randint(0, 59):02d}:00'})
        hrv.append({'date': day.isoformat(), 'value': round(random.gauss(48 + 6 * prog, 4))})
vo2 = []
v = 44.7
for day in days[::6]:
    prog = (day - start).days / 365
    v = 44.7 + 4.6 * prog - (1.4 if 0.08 < prog < 0.22 else 0) + random.uniform(-0.3, 0.3)
    vo2.append({'date': day.isoformat(), 'value': round(v, 1)})

prof = {'first_name': {'runner': 'Alex', 'cyclist': 'Sam', 'lifter': 'Jo'}[kind], 'year': 2026, 'end_date': end.isoformat(),
        'units': 'metric', 'age': 39, 'fitness_age': 36}
for name, obj in [('activities', acts), ('daily', daily), ('sleep', sleep), ('hrv', hrv), ('vo2max', vo2), ('profile', prof)]:
    json.dump(obj, open(os.path.join(OUT, f'{name}.json'), 'w'), indent=0)
print(kind, len(acts), 'activities ->', OUT)
