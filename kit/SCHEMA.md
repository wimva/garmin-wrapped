# Data format for the Garmin Wrapped '26 kit

`compute.py` reads a folder of small, normalized JSON files. Every file and every field is optional: missing
data only means some slides are skipped.

**Easiest: let the adapter write them.** Save each Garmin tool result as returned into `raw/` (see below) and run
`python kit/adapt.py raw data`. It understands camelCase Garmin Connect fields (`activityId`, `startTimeLocal`,
`sleepScores.overall.value`, `hrTimeInZone_1`…) and snake_case connector fields (`id`, `type`, `start_time`,
`duration_seconds`, `distance_meters`, `elevation_gain_meters`, `avg_hr_bpm`, `sleep_seconds`, `sleep_score`,
`sleep_start`, `vo2_max`…), epoch seconds/milliseconds and ISO times (converted to the profile timezone), nested
values, paged or wrapped results, and duplicates. VO2 max values marked `carried_forward` are skipped (not a new
measurement); missing or zero HRV/VO2 values are skipped, never stored as 0. It writes only the fields below;
activity names, devices and all GPS except the rounded start point and requested routes are dropped.
`compute.py` also runs every file through the same normalizers, so slightly different field names still work.

```
raw/profile.json                  first name, year, end date, units, age, fitness age, timezone (any naming)
raw/activities/*.json             activity lists (one file per page)
raw/daily/*.json                  daily summaries
raw/sleep/*.json                  sleep nights
raw/vo2max/*.json                 VO2 max history
raw/hrv/*.json                    HRV history
raw/routes/<activity_id>.json     GPS polyline of one activity, only when compute.py asks
```

Keep `raw/` in the sandbox; never hand it to the user.

Dates are local dates `YYYY-MM-DD`. Times are local ISO `YYYY-MM-DDTHH:MM:SS`. Distances are in metres,
durations in seconds. Only include data from **1 January of the year until today**.

```
data/
  profile.json
  activities.json
  daily.json
  sleep.json
  vo2max.json
  hrv.json
  routes/<activity_id>.json      (only the ids compute.py asks for)
```

## profile.json

```json
{ "first_name": "Alex", "year": 2026, "end_date": "2026-11-20", "units": "metric", "age": 39, "fitness_age": 36,
  "timezone": "Europe/Brussels" }
```

`first_name` appears on slide 1 (leave it out to show "My year on the wrist"). `age` and `fitness_age`
only when the user said yes to showing them. `units` is `metric` or `imperial`.

## activities.json — one object per activity

| field | Garmin field (activity list) | notes |
|---|---|---|
| `id` | `activityId` | |
| `date` | `startTimeLocal[:10]` | |
| `start_local` | `startTimeLocal` (with `T`) | used for the "power hour" |
| `sport` | `activityType.typeKey` | e.g. `running`, `road_biking`, `lap_swimming`, `strength_training`, `padel` |
| `duration_s` | `duration` | |
| `distance_m` | `distance` | 0 or absent for non-distance sports |
| `elevation_gain_m` | `elevationGain` | |
| `avg_hr` | `averageHR` | |
| `calories` | `calories` | |
| `fastest_1k_s` | `fastestSplit_1000` | running only |
| `fastest_mile_s` | `fastestSplit_1609` | |
| `fastest_5k_s` | `fastestSplit_5000` | |
| `fastest_10k_s` | `fastestSplit_10000` | |
| `fastest_half_s` | `fastestSplit_21098` | |
| `fastest_marathon_s` | `fastestSplit_42195` | |
| `hr_zone_s` | `[hrTimeInZone_1 … hrTimeInZone_5]` | array of 5 numbers |
| `start_lat`, `start_lon` | `startLatitude`, `startLongitude` | rounded to 4 decimals is plenty; used only to find the most repeated route, never shown |
| `reps`, `sets`, `volume_kg` | `totalReps`, `totalSets`, summed exercise-set volume | strength only |

Compact is good: `[{"id":1,"date":"2026-01-03","start_local":"2026-01-03T08:12:00","sport":"running","duration_s":1850,"distance_m":5244,...}]`.

## daily.json — one object per day

| field | Garmin field (daily summary) |
|---|---|
| `date` | `calendarDate` |
| `steps` | `movement.steps.value` / `totalSteps` |
| `steps_goal` | `movement.steps.goal` / `dailyStepGoal` |
| `floors` | `movement.floorsAscended.value` / `floorsAscended` |
| `rhr` | `heartRate.restingValue` / `restingHeartRate` |
| `intensity_min` | `moderate + 2 × vigorous` intensity minutes |
| `active_kcal` | `calories.burnedActive` / `activeKilocalories` |

## sleep.json — one object per night (the date you woke up)

| field | Garmin field |
|---|---|
| `date` | `calendarDate` |
| `duration_s` | `sleepTimeSeconds` |
| `score` | `sleepScores.overall.value` |
| `start_local` | `sleepStartTimestampLocal` as local ISO time |

## vo2max.json and hrv.json

`[{"date": "2026-01-06", "value": 44.7}, ...]` — VO2 max from the daily max-metrics (`vo2MaxPreciseValue`),
HRV from the nightly average (`lastNightAvg`). Only real measurements: no carried-forward repeats, no zeros for
nights without a value. VO2 max: weekly points are enough. HRV: every night you have — the optional HRV slide
needs at least 30 nights spread over 3 months (5+ nights per month).

## routes/<activity_id>.json

After the first `compute.py` run, `wrapped.json` lists `routes_to_fetch`: activity ids of the most repeated
route. Fetch the GPS polyline of **one** of them (activity details, `geoPolylineDTO.polyline`, ask for
~400 points), save it as returned to `raw/routes/<id>.json` and rerun `adapt.py` (or save
`[[lat, lon], ...]` straight to `data/routes/<id>.json`).

Route privacy (enforced and tested in `tests/test_route_privacy.py`):
- invalid points (missing, NaN, out of range, 0/0) are dropped;
- exactly the first and last 200 m are removed (interpolated along the line), always;
- a route that is shorter than 1 km, has fewer than 8 valid points, or keeps less than 600 m after trimming gets
  **no route slide**: there is never an untrimmed fallback;
- `wrapped.json` only stores an anonymous shape (x/y between 0 and 1). Raw GPS stays in `raw/` and `data/routes/`,
  never in the plan or the slides; no map, coordinates, street names or addresses are ever drawn.

## Never include

Weight, BMI, body composition, menstrual or pregnancy data, food or hydration logs, exact addresses,
anyone else's data. Do not put coordinates anywhere except `start_lat`/`start_lon` and `routes/`.

## Where the data comes from (two tested connectors)

**Garmin Personal API (Claude Desktop extension by the Garmin School)**
- activities: `search_activities` with `start_date`, `end_date`, `limit: 100`, page with `start`
- daily: `get_daily_summaries` (up to a year per call; split into quarters if the answer is cut off)
- sleep: `get_sleep_range` (31 nights per call)
- HRV: `get_hrv_range`
- fitness age: `get_fitness_age`
- VO2 max: `get_endpoint` → `/metrics-service/metrics/maxmet/daily/<start>/<end>` with `detail: true`
- route: `get_endpoint` → `/activity-service/activity/<id>/details` with `query: {"maxPolylineSize": "400"}`

**Other Garmin MCPs** (e.g. the one that also works in ChatGPT) expose the same Garmin Connect data under other
tool names: look for tools that list activities, daily summaries, sleep, HRV, VO2 max/training status,
fitness age and activity details/GPS.
