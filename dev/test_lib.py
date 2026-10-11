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


class ClosingHook(unittest.TestCase):
    def run_hook(self, vars_, body, fb=("no_promise", "service_error")):  # fb: a brief's failure pair, passed explicitly
        cfg = {"body": body}
        exec(compile(snippets.close_pre_process(fb), "hook", "exec"), {"vars": vars_, "config": cfg})
        return cfg["body"]
    def test_overwrites_free_text_reason(self):
        b = self.run_hook({"outcome": "not_verified", "reason": "declined", "customer_id": "c1"},
                          {"outcome": "not_verified", "reason": "customer refused to provide verification details", "customer_id": "c1"})
        self.assertEqual(b, {"outcome": "not_verified", "reason": "declined", "customer_id": "c1"})
    def test_fallback_when_code_set_nothing(self):
        b = self.run_hook({"customer_id": "c1"}, {"outcome": "x", "reason": "free text", "customer_id": "c1"})
        self.assertEqual((b["outcome"], b["reason"]), ("no_promise", "service_error"))
    def test_no_fallback_leaves_body(self):
        cfg = {"body": {"outcome": "x", "reason": "free text", "customer_id": "c1"}}
        exec(compile(snippets.close_pre_process(), "hook", "exec"), {"vars": {}, "config": cfg})
        self.assertEqual(cfg["body"], {"outcome": "x", "reason": "free text", "customer_id": "c1"})
    def test_promise_has_no_reason(self):
        b = self.run_hook({"outcome": "promise", "reason": "", "customer_id": "c1"}, {"outcome": "promise", "reason": "x", "customer_id": "c1"})
        self.assertNotIn("reason", b)


class LoopGuard(unittest.TestCase):
    def run_guard(self, vars_):
        src = ("def close(key, say):\n    vars['closed_with'] = key\n    return\n"
               "def main():\n" + "".join("    " + l + "\n" for l in snippets.loop_guard('service_error', 3).splitlines()) + "main()\n")
        exec(compile(src, "guard", "exec"), {"vars": vars_})
        return vars_
    def test_counts_and_closes_past_limit(self):
        v = {}
        for _ in range(3): self.run_guard(v)
        self.assertNotIn("closed_with", v)
        self.run_guard(v)
        self.assertEqual((v["loops"], v["closed_with"]), (4, "service_error"))


class ItemsFromKeys(unittest.TestCase):
    V = {"load_account_response.data.products.0.product_id": "p1", "load_account_response.data.products.0.past_due": 365,
         "load_account_response.data.products.0.minimum_payment": 109.5, "load_account_response.data.products.1.product_id": "p2",
         "load_account_response.data.products.1.past_due": 900, "load_account_response.data.ok": "true", "products_x.0.a": 1}
    def test_flattened_keys(self):
        r = cal.items_from_keys(self.V, "products")
        self.assertEqual([x["product_id"] for x in r], ["p1", "p2"]); self.assertEqual(r[0]["past_due"], 365)
    def test_stored_string_wins(self):
        self.assertEqual(cal.items_from_keys({"products": "[{'product_id': 'p9', 'ok': True}]"}, "products"), [{"product_id": "p9", "ok": True}])
    def test_empty(self):
        self.assertEqual(cal.items_from_keys({"a": 1}, "products"), [])


class ClosingHookNames(unittest.TestCase):
    def test_custom_variable_names(self):
        cfg = {"body": {"outcome": "x", "reason": "free text", "customer_id": "c1"}}
        exec(compile(snippets.close_pre_process(outcome_var="close_outcome", reason_var="close_reason", customer_var="cid"), "h", "exec"),
             {"vars": {"close_outcome": "transferred", "close_reason": "restructuring", "cid": "c7"}, "config": cfg})
        self.assertEqual(cfg["body"], {"outcome": "transferred", "reason": "restructuring", "customer_id": "c7"})


class OtherNows(unittest.TestCase):
    """Calendar A, hand-computed from the calendar: 2026-10-16 Fri, 10-17 Sat, 10-23 Fri, 10-26 Mon holiday, 11-10 Tue, 11-11 Wed holiday."""
    def dt(self, y, m, d, hh=11, mm=0): return dt.datetime(y, m, d, hh, mm)
    def test_friday_now_deadlines(self):
        fri = D(2026, 10, 16)
        self.assertEqual(cal.add_bd(fri, 7, HA), D(2026, 10, 28))     # 19,20,21,22,23, (26 holiday), 27, 28
        self.assertEqual(cal.add_bd(fri, 12, HA), D(2026, 11, 4))
    def test_this_friday_on_a_friday_is_today(self):
        d, kind = cal.resolve_phrase("this Friday", D(2026, 10, 16))
        self.assertEqual((d, kind), (D(2026, 10, 16), "this_weekday"))
    def test_next_friday_on_a_friday_is_a_week_later(self):
        self.assertEqual(cal.resolve_phrase("next Friday", D(2026, 10, 16))[0], D(2026, 10, 23))
    def test_saturday_now(self):
        sat = D(2026, 10, 17)
        self.assertEqual(cal.add_bd(sat, 1, HA), D(2026, 10, 19))
        self.assertEqual(cal.add_bd(sat, 7, HA), D(2026, 10, 28))
        self.assertEqual(cal.callback_state(D(2026, 10, 17), "12:00", self.dt(2026, 10, 17), "10:00", "19:00", HA), "day")  # today is no business day
        self.assertEqual(cal.callback_state(D(2026, 10, 19), "10:00", self.dt(2026, 10, 17), "10:00", "19:00", HA), "ok")
    def test_friday_before_holiday_monday_callback(self):
        now = self.dt(2026, 10, 23)
        self.assertEqual(cal.callback_state(D(2026, 10, 26), "11:00", now, "10:00", "19:00", HA), "day")   # holiday
        self.assertEqual(cal.callback_state(D(2026, 10, 27), "10:00", now, "10:00", "19:00", HA), "ok")    # next business day
        self.assertEqual(cal.callback_state(D(2026, 10, 23), "11:30", now, "10:00", "19:00", HA), "ok")
    def test_after_window_closed(self):
        now = self.dt(2026, 10, 14, 19, 30)
        self.assertNotEqual(cal.callback_state(D(2026, 10, 14), "19:45", now, "10:00", "19:00", HA), "ok")
        self.assertEqual(cal.callback_state(D(2026, 10, 15), "10:00", now, "10:00", "19:00", HA), "ok")
    def test_window_edges(self):
        now = self.dt(2026, 10, 14, 11, 0)
        self.assertEqual(cal.callback_state(D(2026, 10, 15), "19:00", now, "10:00", "19:00", HA), "ok")    # both edges included
        self.assertEqual(cal.callback_state(D(2026, 10, 15), "10:00", now, "10:00", "19:00", HA), "ok")
        self.assertEqual(cal.callback_state(D(2026, 10, 15), "19:01", now, "10:00", "19:00", HA), "time")
        self.assertEqual(cal.callback_state(D(2026, 10, 15), "09:59", now, "10:00", "19:00", HA), "time")
    def test_day_before_holiday(self):
        tue = D(2026, 11, 10)
        self.assertEqual(cal.add_bd(tue, 1, HA), D(2026, 11, 12))     # Wed 11 is a holiday
        self.assertEqual(cal.promise_date_state(D(2026, 11, 11), tue, D(2026, 11, 20), HA), "not_business_day")
    def test_tomorrow_on_friday_lands_on_saturday(self):
        fri = D(2026, 10, 23)
        d, kind = cal.resolve_phrase("tomorrow", fri)
        self.assertEqual((d, kind), (D(2026, 10, 24), "tomorrow"))
        self.assertEqual(cal.promise_date_state(d, fri, D(2026, 11, 2), HA), "not_business_day")


class Turkish(unittest.TestCase):
    """Calendar A, today Wednesday 2026-10-14 (so Fri 16, Sat 17, Sun 18, Mon 19, Fri 23). Expectations are worked out from the calendar."""
    def r(self, text, mode="following_week"): return cal.resolve_phrase_tr(text, TODAY, mode)
    def test_relative_days(self):
        self.assertEqual(self.r("bugün"), (TODAY, "today"))
        self.assertEqual(self.r("yarın sabah saat on bir civarı"), (D(2026, 10, 15), "tomorrow"))
        self.assertEqual(self.r("öbür gün"), (D(2026, 10, 16), "day_after_tomorrow"))
        self.assertEqual(self.r("YARIN"), (D(2026, 10, 15), "tomorrow"))   # capital I / İ must fold
    def test_weekdays_and_suffixes(self):
        self.assertEqual(self.r("Cuma'ya"), (D(2026, 10, 16), "weekday"))
        self.assertEqual(self.r("cuma günü"), (D(2026, 10, 16), "weekday"))
        self.assertEqual(self.r("cumartesi"), (D(2026, 10, 17), "weekday"))     # not 'cuma'
        self.assertEqual(self.r("pazartesi"), (D(2026, 10, 19), "weekday"))     # not 'pazar'
        self.assertEqual(self.r("pazar"), (D(2026, 10, 18), "weekday"))
        self.assertEqual(self.r("PERŞEMBE"), (D(2026, 10, 15), "weekday"))
    def test_this_and_next(self):
        self.assertEqual(self.r("bu cuma"), (D(2026, 10, 16), "this_weekday"))
        self.assertEqual(self.r("haftaya cuma"), (D(2026, 10, 23), "next_weekday"))
        self.assertEqual(self.r("haftaya cuma", "next_occurrence"), (D(2026, 10, 16), "next_weekday"))
    def test_day_of_month(self):
        self.assertEqual(self.r("ayın yirmisi"), (D(2026, 10, 20), "day_of_month"))
        self.assertEqual(self.r("20 Ekim"), (D(2026, 10, 20), "day_of_month"))
        self.assertEqual(self.r("yirmi üç Kasım"), (D(2026, 11, 23), "day_of_month"))
        self.assertEqual(self.r("ayın 5'i"), (D(2026, 11, 5), "day_of_month"))   # the 5th is past: next month

    def test_day_of_month_beats_weekday(self):
        self.assertEqual(self.r("Yirmi altısı pazartesi günü ödeyebilirim"), (D(2026, 10, 26), "day_of_month"))
        self.assertEqual(self.r("26 pazartesi"), (D(2026, 10, 26), "day_of_month"))
        self.assertEqual(self.r("pazartesi"), (D(2026, 10, 19), "weekday"))
        self.assertEqual(self.r("haftaya cuma"), (D(2026, 10, 23), "next_weekday"))
        self.assertEqual(self.r("on beşinci perşembe")[0], D(2026, 10, 15))   # the 15th is a Thursday
    def test_nothing(self):
        self.assertEqual(self.r("bilmiyorum"), (None, "none"))
    def test_number_words(self):
        for text, exp in [("bin dokuz yüz seksen dokuz", [1989]), ("yirmi üç", [23]), ("iki bin yirmi altı", [2026]), ("yüz elli", [150]),
                          ("dokuz yüz dört", [904]), ("yirmi üç şubat bin dokuz yüz seksen dokuz", [23, 1989]), ("yirmisi", [20]), ("on beş", [15])]:
            self.assertEqual(cal.numbers_tr(text), exp, text)
    def test_digits(self):
        self.assertEqual(cal.digits_tr("sıfır dokuz sıfır dört"), "0904")
        self.assertEqual(cal.digits_tr("0 9 0 4"), "0904")
    def test_clock(self):
        for text, exp in [("saat on bir buçuk", "11:30"), ("15:30", "15:30"), ("saat 17", "17:00"), ("öğleden sonra üç buçuk", "15:30"),
                          ("akşam altı", "18:00"), ("sabah on", "10:00"), ("on bir", "11:00"), ("yarın sabah on birde", "11:00")]:
            self.assertEqual(cal.hhmm_from_words_tr(text), exp, text)
        self.assertIsNone(cal.hhmm_from_words_tr("sabah"))
    def test_say_date(self):
        self.assertEqual(cal.say_date_tr(D(2026, 10, 16)), "16 Ekim 2026 Cuma")
    def test_dispatch(self):
        self.assertEqual(cal.resolve_phrase_any("tomorrow", TODAY, "en")[0], D(2026, 10, 15))
        self.assertEqual(cal.resolve_phrase_any("yarın", TODAY, "tr")[0], D(2026, 10, 15))


class TurkishFormats(unittest.TestCase):
    """Turkish writes 15.30 for a time, 1.250,50 for an amount and 15.11.2026 for a date. Expectations by hand."""
    def test_numeric_dates(self):
        r = lambda t: cal.resolve_phrase_tr(t, TODAY)
        self.assertEqual(r("15.11.2026"), (D(2026, 11, 15), "numeric_date"))
        self.assertEqual(r("15/11/2026"), (D(2026, 11, 15), "numeric_date"))
        self.assertEqual(r("3.5.2027"), (D(2027, 5, 3), "numeric_date"))
        self.assertEqual(r("15.11"), (D(2026, 11, 15), "numeric_date"))
        self.assertEqual(r("26.10.26"), (D(2026, 10, 26), "numeric_date"))
        self.assertEqual(r("yarın saat 10.11")[1], "tomorrow")      # a time, not 10 November
    def test_clock_with_dot(self):
        for text, exp in [("saat 15.30", "15:30"), ("15.30", "15:30"), ("9.05", "09:05"), ("saat 15:30", "15:30"), ("yarın saat 11.00", "11:00")]:
            self.assertEqual(cal.hhmm_from_words_tr(text), exp, text)
        self.assertEqual(cal.hhmm_from_words_tr("saat on bir buçuk"), "11:30")
    def test_amounts_in_digits(self):
        for text, exp in [("1.250,50", 1250.5), ("1250,5", 1250.5), ("1250", 1250.0), ("1.250", 1250.0), ("250,00 TL", 250.0), ("365,50", 365.5),
                          ("300 lira", 300.0), ("365.50", 365.5), ("1.250.000", 1250000.0)]:
            self.assertEqual(cal.amount_tr(text), exp, text)
    def test_amounts_in_words(self):
        for text, exp in [("bin iki yüz elli lira", 1250.0), ("üç yüz altmış beş lira elli kuruş", 365.5), ("yüz kırk lira", 140.0), ("on bin", 10000.0)]:
            self.assertEqual(cal.amount_tr(text), exp, text)
        self.assertIsNone(cal.amount_tr("bilmiyorum"))
    def test_say_amount(self):
        self.assertEqual(cal.say_amount_tr(1250.5), "1.250,50 TL")
        self.assertEqual(cal.say_amount_tr(365), "365 TL")
        self.assertEqual(cal.say_amount_tr(109.5), "109,50 TL")
        self.assertEqual(cal.say_amount_tr(1250000), "1.250.000 TL")


class Pruning(unittest.TestCase):
    def run_code(self, body, spec=None, now="2026-10-14T11:00"):
        v = {"now": now}
        exec(compile(snippets.code(body, spec or {}), "node", "exec"), {"vars": v})
        return v
    def test_small_and_correct(self):
        body = "vars['x'] = say_date(add_bd(parse_now(vars['now']).date(), 7, set(SPEC['h'])))"
        self.assertLess(len(snippets.code(body, {"h": []})), 4000)
        self.assertEqual(self.run_code(body, {"h": []})["x"], "Friday 23 October 2026")
    def test_module_level_updates_follow_their_table(self):
        v = self.run_code("vars['d'] = resolve_phrase('on the twenty first', parse_now(vars['now']).date())[0].isoformat()")
        self.assertEqual(v["d"], "2026-10-21")                       # needs _ORD.update(...) that sits next to the table
    def test_turkish_is_carried_only_when_used(self):
        en = snippets.code("vars['x'] = resolve_phrase('tomorrow', parse_now(vars['now']).date())[1]")
        self.assertNotIn("def resolve_phrase_tr", en)
        v = self.run_code("vars['y'] = resolve_phrase_tr('haftaya cuma', parse_now(vars['now']).date())[0].isoformat(); vars['t'] = hhmm_from_words_tr('saat 15.30'); vars['a'] = amount_tr('1.250,50')")
        self.assertEqual((v["y"], v["t"], v["a"]), ("2026-10-23", "15:30", 1250.5))
    def test_prune_false_keeps_everything(self):
        self.assertIn("def resolve_phrase_tr", snippets.code("pass", {}, prune=False))


if __name__ == "__main__":
    unittest.main(verbosity=1)
