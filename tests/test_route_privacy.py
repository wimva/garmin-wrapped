import json, math, unittest
from helpers import CENTER, loop, line, runner_data, tmpdir
import compute


def geo_like(v):
    return isinstance(v, (int, float)) and (abs(v - CENTER[0]) < 1 or abs(v - CENTER[1]) < 1) and abs(v) > 1.5


class TrimRoute(unittest.TestCase):
    def test_short_route_is_skipped(self):
        self.assertIsNone(compute.trim_route(line(km=0.9)))          # < 200 + 600 + 200 m

    def test_sparse_route_is_skipped(self):
        self.assertIsNone(compute.trim_route(line(km=5, n=4)))        # long but only 5 points

    def test_few_points_never_returned_untrimmed(self):
        for n in (2, 5, 10, 20):
            r = compute.trim_route(line(km=3, n=n))
            if r is not None:
                self.assertGreaterEqual(compute.hav(tuple(line(3, n)[0]), r[0]), 199)

    def test_invalid_coordinates_are_dropped(self):
        pts = loop(5)
        pts[10] = [None, 4.3]; pts[20] = [float('nan'), 4.3]; pts[30] = [999, 4.3]; pts[40] = [0, 0]; pts[50] = 'x'
        r = compute.trim_route(pts)
        self.assertIsNotNone(r)
        for lat, lon in r:
            self.assertTrue(math.isfinite(lat) and -90 <= lat <= 90 and -180 <= lon <= 180 and abs(lat) > 1)

    def test_only_invalid_is_skipped(self):
        self.assertIsNone(compute.trim_route([[None, None], [999, 999], [0, 0]] * 10))

    def test_loop_endpoints_are_200m_in(self):
        raw = loop(5)
        r = compute.trim_route(raw)
        self.assertIsNotNone(r)
        start, end = tuple(raw[0]), tuple(raw[-1])
        # the first and last kept points sit 200 m along the route from the real start/finish
        self.assertGreaterEqual(compute.hav(start, r[0]), 150)
        self.assertGreaterEqual(compute.hav(end, r[-1]), 150)
        along = compute.hav(tuple(raw[0]), tuple(raw[1]))
        self.assertGreater(len(r), 50)

    def test_normal_route_trims_exactly_200m(self):
        raw = line(km=3, n=300)
        r = compute.trim_route(raw)
        self.assertAlmostEqual(compute.hav(tuple(raw[0]), r[0]), 200, delta=2)
        self.assertAlmostEqual(compute.hav(tuple(raw[-1]), r[-1]), 200, delta=2)
        kept = sum(compute.hav(r[i - 1], r[i]) for i in range(1, len(r)))
        self.assertAlmostEqual(kept, 2600, delta=10)


class Shape(unittest.TestCase):
    def test_shape_is_unit_box_and_not_geographic(self):
        s = compute.route_shape(compute.trim_route(loop(5)))
        flat = [v for p in s for v in p]
        self.assertTrue(all(0 <= v <= 1 for v in flat))
        self.assertFalse(any(geo_like(v) for v in flat))
        self.assertAlmostEqual(max(max(x for x, _ in s), max(y for _, y in s)), 1, places=3)


class Plan(unittest.TestCase):
    def plan(self, route):
        d = tmpdir()
        runner_data(d, route=route)
        return compute.plan(compute.Year(d)), d

    def test_plan_has_no_coordinates(self):
        p, _ = self.plan(loop(5))
        r = [s for s in p['slides'] if s['module'] == 'route']
        self.assertEqual(len(r), 1)
        self.assertNotIn('points', r[0])
        text = json.dumps(p)
        for v in (CENTER[0], CENTER[1]):
            self.assertNotIn(f'{v:.2f}', text)
        self.assertFalse(any(geo_like(v) for pt in r[0]['shape'] for v in pt))

    def test_unsafe_route_means_no_route_slide(self):
        p, _ = self.plan(line(km=0.7))
        self.assertFalse([s for s in p['slides'] if s['module'] == 'route'])
        self.assertEqual(p['routes_to_fetch'], [])          # files existed: don't ask again, just skip

    def test_missing_route_asks_for_one(self):
        p, _ = self.plan(None)
        self.assertFalse([s for s in p['slides'] if s['module'] == 'route'])
        self.assertTrue(p['routes_to_fetch'])

    def test_no_start_coordinates_in_plan(self):
        p, _ = self.plan(loop(5))
        self.assertNotIn('start_lat', json.dumps(p))


if __name__ == '__main__':
    unittest.main()
