"""Unit tests for builder/lib. Expected values are worked out by hand from the two calendars, not taken from the code.
    python3 dev/test_lib.py
Calendar A: holidays 2026-10-26, 2026-11-11, 2026-11-26, 2026-12-25, 2027-01-01. Calendar M: 2026-10-20, 2026-11-03, 2026-11-19, 2026-12-24, 2027-01-04.
"""
import datetime as dt, pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "builder" / "lib"))
import cal, snippets
D = dt.date
HA = {"2026-10-26", "2026-11-11", "2026-11-26", "2026-12-25", "2027-01-01"}
HM = {"2026-10-20", "2026-11-03", "2026-11-19", "2026-12-24", "2027-01-04"}
NOW = dt.datetime(2026, 10, 14, 11, 0)   # Wednesday
TODAY = NOW.date()


class Calendar(unittest.TestCase):
    def test_deadlines_A(self):
        self.assertEqual(cal.add_bd(TODAY, 7, HA), D(2026, 10, 23))
        self.assertEqual(cal.add_bd(TODAY, 12, HA), D(2026, 11, 2))   # 26 Oct is a holiday
    def test_deadlines_M(self):
        self.assertEqual(cal.add_bd(TODAY, 5, HM), D(2026, 10, 22))   # 20 Oct skipped
        self.assertEqual(cal.add_bd(TODAY, 10, HM), D(2026, 10, 29))
    def test_weekend_and_zero(self):
        self.assertEqual(cal.add_bd(D(2026, 10, 16), 1, HA), D(2026, 10, 19))
        self.assertEqual(cal.add_bd(TODAY, 0, HA), TODAY)
    def test_on_or_after(self):
        self.assertEqual(cal.on_or_after_bd(D(2026, 10, 24), HA), D(2026, 10, 27))  # Sat, Sun, holiday Mon
        self.assertEqual(cal.on_or_after_bd(D(2026, 10, 20), HM), D(2026, 10, 21))
    def test_last_bd_of_week(self):
        self.assertEqual(cal.last_bd_of_week(TODAY, HA), D(2026, 10, 16))
        self.assertEqual(cal.last_bd_of_week(D(2026, 10, 27), HA), D(2026, 10, 30))
        self.assertEqual(cal.last_bd_of_week(D(2026, 11, 9), {"2026-11-13"}), D(2026, 11, 12))
    def test_say(self):
        self.assertEqual(cal.say_date(D(2026, 10, 16)), "Friday 16 October 2026")


class Phrases(unittest.TestCase):
    def r(self, s, mode="following_week"): return cal.resolve_phrase(s, TODAY, mode)
    def test_relative(self):
        self.assertEqual(self.r("tomorrow morning around eleven"), (D(2026, 10, 15), "tomorrow"))
        self.assertEqual(self.r("the day after tomorrow")[0], D(2026, 10, 16))
        self.assertEqual(self.r("today")[0], TODAY)
    def test_weekdays(self):
        self.assertEqual(self.r("this Friday")[0], D(2026, 10, 16))
        self.assertEqual(self.r("next Friday")[0], D(2026, 10, 23))        # Friday of the following calendar week
        self.assertEqual(self.r("next Friday", "next_occurrence")[0], D(2026, 10, 16))
        self.assertEqual(self.r("next Monday")[0], D(2026, 10, 19 + 0))    # Monday of the following week
        self.assertEqual(self.r("Friday")[0], D(2026, 10, 16))
        self.assertEqual(self.r("this Monday")[0], D(2026, 10, 12))        # in the past: the caller rejects it
    def test_day_of_month(self):
        self.assertEqual(self.r("Tuesday the 20th")[0], D(2026, 10, 20))
        self.assertEqual(self.r("the twentieth")[0], D(2026, 10, 20))
        self.assertEqual(self.r("October 20")[0], D(2026, 10, 20))
        self.assertEqual(self.r("20th of October")[0], D(2026, 10, 20))
        self.assertEqual(self.r("Monday 2 November")[0], D(2026, 11, 2))
        self.assertEqual(self.r("the 5th")[0], D(2026, 11, 5))             # 5 Oct has passed: next month
        self.assertEqual(self.r("the twenty first")[0], D(2026, 10, 21))
    def test_iso_and_none(self):
        self.assertEqual(self.r("2026-11-02")[0], D(2026, 11, 2))
        self.assertEqual(self.r("sometime later")[0], None)
        self.assertEqual(self.r("end of the month")[0], None)
        self.assertEqual(self.r("")[0], None)
    def test_time_words(self):
        for s, want in (("eleven in the morning", "11:00"), ("around eleven", "11:00"), ("3 pm", "15:00"), ("15:30", "15:30"),
                        ("half past two in the afternoon", "14:30"), ("noon", None), ("morning", None)):
            self.assertEqual(cal.hhmm_from_words(s), want, s)


class Windows(unittest.TestCase):
    def cb(self, d, t, now=NOW, start="09:00", end="17:00", h=HM): return cal.callback_state(d, t, now, start, end, h)
    def test_inclusive_edges(self):
        self.assertEqual(self.cb(D(2026, 10, 15), "09:00"), "ok")
        self.assertEqual(self.cb(D(2026, 10, 15), "17:00"), "ok")
        self.assertEqual(self.cb(D(2026, 10, 15), "08:59"), "time")
        self.assertEqual(self.cb(D(2026, 10, 15), "17:01"), "time")
        self.assertEqual(self.cb(D(2026, 10, 15), "10:00", start="10:00", end="19:00", h=HA), "ok")
        self.assertEqual(self.cb(D(2026, 10, 15), "19:00", start="10:00", end="19:00", h=HA), "ok")
        self.assertEqual(self.cb(D(2026, 10, 15), "09:59", start="10:00", end="19:00", h=HA), "time")
    def test_later_than_now(self):
        self.assertEqual(self.cb(TODAY, "11:00"), "past")      # equal to now is not later
        self.assertEqual(self.cb(TODAY, "11:01"), "ok")
        self.assertEqual(self.cb(TODAY, "10:00"), "past")
    def test_days(self):
        self.assertEqual(self.cb(D(2026, 10, 16), "11:00"), "day")
        fri = dt.datetime(2026, 10, 16, 9, 0)
        self.assertEqual(self.cb(D(2026, 10, 19), "11:00", now=fri), "ok")            # next business day after Friday is Monday
        self.assertEqual(self.cb(D(2026, 10, 17), "11:00", now=fri), "day")
        tue = dt.datetime(2026, 10, 19, 9, 0)
        self.assertEqual(self.cb(D(2026, 10, 21), "11:00", now=tue), "ok")            # 20 Oct is a holiday in M
        self.assertEqual(self.cb(D(2026, 10, 20), "11:00", now=tue), "day")
        sat = dt.datetime(2026, 10, 17, 9, 0)
        self.assertEqual(self.cb(D(2026, 10, 17), "11:00", now=sat), "day")            # today is not a business day
        self.assertEqual(self.cb(D(2026, 10, 19), "11:00", now=sat), "ok")
        self.assertEqual(self.cb(D(2026, 10, 15), "11am"), "time")
    def test_promise_dates(self):
        dl = D(2026, 10, 23)
        s = lambda d: cal.promise_date_state(d, TODAY, dl, HA)
        self.assertEqual(s(TODAY), "ok"); self.assertEqual(s(dl), "ok"); self.assertEqual(s(D(2026, 10, 24)), "not_business_day")
        self.assertEqual(s(D(2026, 10, 26)), "not_business_day"); self.assertEqual(s(D(2026, 10, 27)), "after_deadline")
        self.assertEqual(s(D(2026, 10, 13)), "past")


class Bands(unittest.TestCase):
    B = [{"min": 1, "max": 7, "name": "early", "deadline_bd": 12, "attempts": 1}, {"min": 8, "max": 45, "name": "late", "deadline_bd": 7, "attempts": 2}]
    def test_edges(self):
        for n, want in ((1, "early"), (7, "early"), (8, "late"), (45, "late"), (46, None), (0, None), ("14", "late"), (14.0, "late"), (None, None), ("x", None)):
            b = cal.band_for(n, self.B); self.assertEqual(b and b["name"], want, n)
    def test_floor(self):
        f = {"credit_card": "minimum_payment", "personal_loan": "instalment_amount", "car_loan": "instalment_amount"}
        self.assertEqual(cal.floor_for({"type": "credit_card", "minimum_payment": 66}, f), 66)
        self.assertEqual(cal.floor_for({"type": "car_loan", "instalment_amount": 25}, f), 25)
        self.assertIsNone(cal.floor_for({"type": "mortgage"}, f))


class Embedding(unittest.TestCase):
    def test_code_text_runs_like_a_platform_code_node(self):
        body = ("today = parse_now(vars['now']).date()\n"
                "vars['deadline'] = add_bd(today, SPEC['n'], set(SPEC['hol'])).isoformat()\n"
                "vars['when'] = resolve_phrase('tomorrow', today)[0].isoformat()\n")
        v = {"now": "2026-10-14T11:00"}
        exec(compile(snippets.code(body, {"n": 7, "hol": sorted(HA)}), "node", "exec"), {"vars": v})
        self.assertEqual(v, {"now": "2026-10-14T11:00", "deadline": "2026-10-23", "when": "2026-10-15"})


if __name__ == "__main__":
    unittest.main(verbosity=1)
