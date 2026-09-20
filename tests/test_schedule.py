"""The update cadence.

The site is supposed to refresh every 10 minutes from 11:00 AM Saturday
through 3:00 AM Sunday US Central, and once a day otherwise. GitHub cron is
UTC only, so update.yml schedules a wider UTC span and a guard step trims it
back to the Central window. This checks the two together, across the November
DST change, by replaying a whole season minute-slot by minute-slot.
"""

import datetime as dt
import os
import re
import unittest
from zoneinfo import ZoneInfo

WORKFLOW = os.path.join(
    os.path.dirname(__file__), "..", ".github", "workflows", "update.yml"
)
CENTRAL = ZoneInfo("America/Chicago")
DAILY = "0 13 * * *"


def crons() -> list[str]:
    with open(WORKFLOW, encoding="utf-8") as fh:
        return re.findall(r"- cron: '([^']+)'", fh.read())


def _field_matches(field: str, value: int, lo: int, hi: int) -> bool:
    for part in field.split(","):
        if part == "*":
            return True
        step = 1
        if "/" in part:
            part, raw_step = part.split("/", 1)
            step = int(raw_step)
        if part == "*":
            start, end = lo, hi
        elif "-" in part:
            start, end = (int(x) for x in part.split("-", 1))
        else:
            start = end = int(part)
            if step == 1:
                if value == start:
                    return True
                continue
        if start <= value <= end and (value - start) % step == 0:
            return True
    return False


def fires(cron: str, moment: dt.datetime) -> bool:
    """Does this cron fire at this UTC minute?"""
    minute, hour, dom, month, dow = cron.split()
    return (
        _field_matches(minute, moment.minute, 0, 59)
        and _field_matches(hour, moment.hour, 0, 23)
        and _field_matches(dom, moment.day, 1, 31)
        and _field_matches(month, moment.month, 1, 12)
        and _field_matches(dow, moment.weekday() + 1 if moment.weekday() < 6 else 0, 0, 6)
    )


def guard_passes(cron: str, moment: dt.datetime) -> bool:
    """The workflow's window step, in Python."""
    if cron == DAILY:
        return True
    local = moment.astimezone(CENTRAL)
    dow = local.isoweekday()              # 1=Mon .. 7=Sun
    hm = local.hour * 100 + local.minute
    if dow == 6 and hm >= 1100:
        return True
    if dow == 7 and hm < 300:
        return True
    return False


def builds_at(moment: dt.datetime) -> list[str]:
    return [c for c in crons() if fires(c, moment) and guard_passes(c, moment)]


def in_saturday_window(local: dt.datetime) -> bool:
    dow = local.isoweekday()
    hm = local.hour * 100 + local.minute
    return (dow == 6 and hm >= 1100) or (dow == 7 and hm < 300)


def season_slots(step_minutes: int = 10):
    moment = dt.datetime(2026, 8, 1, tzinfo=dt.timezone.utc)
    end = dt.datetime(2027, 1, 10, tzinfo=dt.timezone.utc)
    while moment < end:
        yield moment
        moment += dt.timedelta(minutes=step_minutes)


class CronParsingTests(unittest.TestCase):
    def test_workflow_declares_the_expected_crons(self):
        self.assertEqual(
            crons(),
            ["*/10 16-23 * * 6", "*/10 0-9 * * 0", DAILY],
        )

    def test_field_matcher(self):
        self.assertTrue(_field_matches("*/10", 20, 0, 59))
        self.assertFalse(_field_matches("*/10", 25, 0, 59))
        self.assertTrue(_field_matches("16-23", 16, 0, 23))
        self.assertFalse(_field_matches("16-23", 15, 0, 23))
        self.assertTrue(_field_matches("*", 7, 0, 23))
        self.assertTrue(_field_matches("6", 6, 0, 6))


class WindowTests(unittest.TestCase):
    def test_every_slot_in_the_saturday_window_builds(self):
        missed = []
        for moment in season_slots():
            local = moment.astimezone(CENTRAL)
            if in_saturday_window(local) and not builds_at(moment):
                missed.append(local.strftime("%Y-%m-%d %H:%M %Z"))
        self.assertEqual(missed[:5], [], f"{len(missed)} uncovered slots")

    def test_nothing_outside_the_window_builds_except_the_daily_run(self):
        strays = []
        for moment in season_slots():
            local = moment.astimezone(CENTRAL)
            if in_saturday_window(local):
                continue
            extra = [c for c in builds_at(moment) if c != DAILY]
            if extra:
                strays.append((local.strftime("%Y-%m-%d %H:%M %Z"), extra))
        self.assertEqual(strays[:5], [], f"{len(strays)} runs outside the window")

    def test_the_window_runs_every_ten_minutes(self):
        # A representative Saturday in each of CDT and CST.
        for saturday in (dt.date(2026, 10, 10), dt.date(2026, 11, 21)):
            start = dt.datetime.combine(saturday, dt.time(11, 0), tzinfo=CENTRAL)
            slots = [start + dt.timedelta(minutes=10 * i) for i in range(16 * 6)]
            built = [s for s in slots if builds_at(s.astimezone(dt.timezone.utc))]
            self.assertEqual(len(built), len(slots), saturday)
            self.assertEqual(
                built[0].strftime("%a %H:%M"), "Sat 11:00", saturday
            )
            self.assertEqual(
                built[-1].strftime("%a %H:%M"), "Sun 02:50", saturday
            )

    def test_the_window_closes_at_three_am(self):
        for saturday in (dt.date(2026, 10, 10), dt.date(2026, 11, 21)):
            sunday = saturday + dt.timedelta(days=1)
            at_250 = dt.datetime.combine(sunday, dt.time(2, 50), tzinfo=CENTRAL)
            at_300 = dt.datetime.combine(sunday, dt.time(3, 0), tzinfo=CENTRAL)
            self.assertTrue(builds_at(at_250.astimezone(dt.timezone.utc)), saturday)
            self.assertFalse(
                [c for c in builds_at(at_300.astimezone(dt.timezone.utc)) if c != DAILY],
                saturday,
            )

    def test_the_window_opens_at_eleven(self):
        for saturday in (dt.date(2026, 10, 10), dt.date(2026, 11, 21)):
            at_1050 = dt.datetime.combine(saturday, dt.time(10, 50), tzinfo=CENTRAL)
            at_1100 = dt.datetime.combine(saturday, dt.time(11, 0), tzinfo=CENTRAL)
            self.assertFalse(
                [c for c in builds_at(at_1050.astimezone(dt.timezone.utc)) if c != DAILY],
                saturday,
            )
            self.assertTrue(builds_at(at_1100.astimezone(dt.timezone.utc)), saturday)

    def test_the_dst_change_weekend_is_covered(self):
        # Clocks go back on Sunday 1 November 2026 at 02:00 local, so that
        # Sunday has two 01:xx hours - both are inside the window.
        saturday = dt.datetime(2026, 10, 31, 11, 0, tzinfo=CENTRAL)
        slots = []
        moment = saturday.astimezone(dt.timezone.utc)
        while moment.astimezone(CENTRAL) < dt.datetime(2026, 11, 1, 3, 0, tzinfo=CENTRAL):
            slots.append(moment)
            moment += dt.timedelta(minutes=10)
        self.assertTrue(all(builds_at(s) for s in slots))
        # 16 hours of wall-clock plus the repeated hour
        self.assertEqual(len(slots), 17 * 6)

    def test_there_is_exactly_one_daily_run_per_day(self):
        days = {}
        for moment in season_slots():
            if DAILY in builds_at(moment):
                days.setdefault(moment.date(), 0)
                days[moment.date()] += 1
        self.assertTrue(days)
        self.assertEqual(set(days.values()), {1})


if __name__ == "__main__":
    unittest.main(verbosity=2)
