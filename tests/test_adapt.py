import json, os, unittest
from helpers import tmpdir, write
import adapt, compute


CHATGPT_ACTIVITIES = {'activities': [
    {'id': 1, 'name': 'Borsbeek Running', 'type': 'running', 'start_time': '2026-03-02T07:15:00Z', 'duration_seconds': 1800,
     'distance_meters': 5100, 'elevation_gain_meters': 12, 'avg_hr_bpm': 148, 'calories': 410},
    {'id': 2, 'type': 'Road Biking', 'start_time': 1772607600000, 'duration_seconds': 3600, 'distance_meters': 30000}],
    'next_page': None}
GARMIN_ACTIVITY = {'activityId': 3, 'activityName': 'Home loop', 'activityType': {'typeKey': 'running'},
                   'startTimeLocal': '2026-11-19 08:21:29', 'startTimeGMT': '2026-11-19 07:21:29', 'duration': 1850.7,
                   'distance': 5244.06, 'elevationGain': 13, 'averageHR': 140, 'calories': 411, 'fastestSplit_1000': 329.9,
                   'fastestSplit_5000': 1744.4, 'hrTimeInZone_1': 444, 'hrTimeInZone_2': 1268, 'hrTimeInZone_3': 84,
                   'hrTimeInZone_4': 22, 'hrTimeInZone_5': 0, 'startLatitude': 51.198788, 'startLongitude': 4.484269,
                   'ownerFullName': 'Someone', 'deviceId': 123}
CHATGPT_SLEEP = [{'date': '2026-11-10', 'sleep_seconds': 25560, 'sleep_score': 60, 'sleep_start': 1794259120000}]
GARMIN_SLEEP = [{'calendarDate': '2026-11-11', 'sleepTimeSeconds': 28080, 'sleepScores': {'overall': {'value': 79}},
                 'sleepStartTimestampLocal': 1794350637000}]
CHATGPT_VO2 = [{'date': '2026-01-06', 'vo2_max': 44.7}, {'date': '2026-01-07', 'vo2_max': 44.7, 'carried_forward': True},
               {'date': '2026-02-02', 'vo2_max': 43.8}]
GARMIN_VO2 = [{'generic': {'calendarDate': '2026-03-02', 'vo2MaxPreciseValue': 43.5}, 'cycling': None}]
GARMIN_DAILY = {'data': [{'calendarDate': '2026-11-10', 'movement': {'steps': {'goal': 10330, 'value': 7726}, 'floorsAscended': {'value': 8}},
                          'heartRate': {'restingValue': 57}, 'intensityMinutes': {'moderate': 10, 'vigorous': 5},
                          'calories': {'burnedActive': 357}}]}
SNAKE_DAILY = [{'date': '2026-11-11', 'total_steps': 9146, 'resting_heart_rate': 54, 'floors_ascended': 12,
                'active_kilocalories': 200, 'moderate_intensity_minutes': 0, 'vigorous_intensity_minutes': 30}]
HRV = {'hrvSummaries': [{'calendarDate': '2026-11-10', 'lastNightAvg': 48}, {'calendarDate': '2026-11-11', 'lastNightAvg': None},
                        {'calendarDate': '2026-11-12', 'last_night_avg': 51}]}


class Adapt(unittest.TestCase):
    def run_adapt(self, tz='Europe/Brussels'):
        raw, data = tmpdir(), tmpdir()
        write(raw, 'profile.json', {'firstName': 'Wim Van', 'timeZone': tz, 'measurementSystem': 'metric', 'fitnessAge': 36.05})
        write(raw, 'activities/page1.json', CHATGPT_ACTIVITIES)
        write(raw, 'activities/page2.json', [GARMIN_ACTIVITY, GARMIN_ACTIVITY])          # duplicate on purpose
        write(raw, 'sleep/a.json', CHATGPT_SLEEP)
        write(raw, 'sleep/b.json', GARMIN_SLEEP)
        write(raw, 'vo2max/a.json', CHATGPT_VO2)
        write(raw, 'vo2max/b.json', GARMIN_VO2)
        write(raw, 'daily/a.json', GARMIN_DAILY)
        write(raw, 'daily/b.json', SNAKE_DAILY)
        write(raw, 'hrv/a.json', HRV)
        write(raw, 'routes/3.json', {'geoPolylineDTO': {'polyline': [{'lat': 51.19, 'lon': 4.48, 'time': 1}, {'lat': None, 'lon': 4}]}})
        out = adapt.adapt(raw, data)
        return out, data

    def test_snake_case_activity(self):
        out, _ = self.run_adapt()
        a = {x['id']: x for x in out['activities']}[1]
        self.assertEqual(a['sport'], 'running')
        self.assertEqual(a['start_local'], '2026-03-02T08:15:00')       # Z converted to Europe/Brussels
        self.assertEqual((a['duration_s'], a['distance_m'], a['elevation_gain_m'], a['avg_hr']), (1800, 5100, 12, 148))
        self.assertNotIn('name', a)

    def test_epoch_ms_and_sport_names(self):
        out, _ = self.run_adapt()
        b = {x['id']: x for x in out['activities']}[2]
        self.assertEqual(b['sport'], 'road_biking')
        self.assertEqual(compute.family(b['sport']), 'cycling')
        self.assertTrue(b['start_local'].startswith('2026-03-04T'))

    def test_camel_case_activity_and_dedupe(self):
        out, _ = self.run_adapt()
        acts = [x for x in out['activities'] if x['id'] == 3]
        self.assertEqual(len(acts), 1)
        a = acts[0]
        self.assertEqual(a['start_local'], '2026-11-19T08:21:29')
        self.assertEqual(a['fastest_1k_s'], 329.9)
        self.assertEqual(a['hr_zone_s'], [444, 1268, 84, 22, 0])
        self.assertEqual((a['start_lat'], a['start_lon']), (51.1988, 4.4843))           # rounded, grouping only
        for k in ('activityName', 'ownerFullName', 'deviceId', 'name'):
            self.assertNotIn(k, a)

    def test_sleep_both_formats(self):
        out, _ = self.run_adapt()
        s = {x['date']: x for x in out['sleep']}
        self.assertEqual((s['2026-11-10']['duration_s'], s['2026-11-10']['score']), (25560, 60))
        self.assertTrue(s['2026-11-10']['start_local'].startswith('2026-11-09T22:'))   # epoch ms (UTC) → Brussels
        self.assertEqual((s['2026-11-11']['duration_s'], s['2026-11-11']['score']), (28080, 79))
        self.assertTrue(s['2026-11-11']['start_local'].startswith('2026-11-10T22:'))   # *Local timestamp kept as wall time

    def test_vo2_skips_carried_forward(self):
        out, _ = self.run_adapt()
        self.assertEqual([(x['date'], x['value']) for x in out['vo2max']],
                         [('2026-01-06', 44.7), ('2026-02-02', 43.8), ('2026-03-02', 43.5)])

    def test_daily_nested_and_snake(self):
        out, _ = self.run_adapt()
        d = {x['date']: x for x in out['daily']}
        self.assertEqual((d['2026-11-10']['steps'], d['2026-11-10']['rhr'], d['2026-11-10']['intensity_min']), (7726, 57, 20))
        self.assertEqual((d['2026-11-11']['steps'], d['2026-11-11']['intensity_min'], d['2026-11-11']['floors']), (9146, 60, 12))

    def test_hrv_missing_not_zero(self):
        out, _ = self.run_adapt()
        self.assertEqual([x['value'] for x in out['hrv']], [48, 51])

    def test_profile(self):
        out, _ = self.run_adapt()
        self.assertEqual(out['profile']['first_name'], 'Wim')
        self.assertEqual(out['profile']['fitness_age'], 36.0)

    def test_routes_normalized(self):
        _, data = self.run_adapt()
        self.assertEqual(json.load(open(os.path.join(data, 'routes', '3.json'))), [[51.19, 4.48]])

    def test_compute_accepts_unnormalized_files(self):
        d = tmpdir()
        write(d, 'activities.json', CHATGPT_ACTIVITIES)
        write(d, 'sleep.json', CHATGPT_SLEEP)
        write(d, 'vo2max.json', CHATGPT_VO2)
        write(d, 'profile.json', {'year': 2026, 'end_date': '2026-11-20'})
        y = compute.Year(d)
        self.assertEqual(len(y.acts), 2)
        self.assertEqual(len(y.vo2), 2)
        self.assertEqual(y.sleep[0]['duration_s'], 25560)

    def test_normalized_data_is_unchanged(self):
        a = {'id': 7, 'date': '2026-05-01', 'start_local': '2026-05-01T07:00:00', 'sport': 'running', 'duration_s': 1500.0,
             'distance_m': 4000.0, 'hr_zone_s': [1, 2, 3, 4, 5], 'fastest_5k_s': 1500.0}
        self.assertEqual(adapt.norm_activity(a, adapt.Clock()), a)


if __name__ == '__main__':
    unittest.main()
