import datetime as dt, unittest
from helpers import runner_data, tmpdir
import compute


def nights(start, n, value=lambda k: 45 + k * 0.05, every=1):
    return [{'date': (start + dt.timedelta(days=k * every)).isoformat(), 'value': value(k)} for k in range(n)]


def hrv_slide(hrv):
    d = tmpdir()
    runner_data(d, hrv=hrv)
    y = compute.Year(d)
    return [s for _, s in compute.build_candidates(y) if s.get('key') == 'hrv'], y


class HRV(unittest.TestCase):
    def test_complete_history_gives_a_slide(self):
        c, y = hrv_slide(nights(dt.date(2026, 1, 1), 300))
        self.assertEqual(len(c), 1)
        s = c[0]
        self.assertEqual(s['module'], 'trend')
        st = compute.hrv_stats(y)
        self.assertEqual(st['nights'], 300)
        self.assertGreater(st['last'], st['first'])
        self.assertIn('ms', s['body'])
        self.assertGreaterEqual(len(s['series']), 3)

    def test_partial_history_is_excluded(self):
        c, _ = hrv_slide(nights(dt.date(2026, 3, 1), 20))
        self.assertEqual(c, [])

    def test_spread_too_thin_is_excluded(self):           # 40 nights but only 2 months with enough nights
        c, _ = hrv_slide(nights(dt.date(2026, 5, 1), 40, every=1)[:40])
        self.assertEqual(c, [])

    def test_missing_history_is_excluded(self):
        c, _ = hrv_slide(None)
        self.assertEqual(c, [])

    def test_missing_nights_are_not_zero(self):
        h = nights(dt.date(2026, 1, 1), 120, value=lambda k: 50)
        for k in range(0, 120, 3):
            h[k]['value'] = None if k % 2 else 0          # gaps: must be skipped, not averaged as 0
        c, y = hrv_slide(h)
        st = compute.hrv_stats(y)
        self.assertAlmostEqual(st['avg'], 50)
        self.assertEqual(st['nights'], 80)

    def test_uses_ranking(self):
        c, y = hrv_slide(nights(dt.date(2026, 1, 1), 300))
        scores = [sc for sc, s in compute.build_candidates(y) if s.get('key') == 'hrv']
        self.assertTrue(0 < scores[0] < 95)


if __name__ == '__main__':
    unittest.main()
