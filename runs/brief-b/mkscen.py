import json
FRI = "2026-10-16T11:00"   # Friday
PRE_HOL = "2026-10-23T18:30"  # Friday before holiday Mon 26 Oct, after... callback window open till 19:00
LATE = "2026-10-14T19:30"  # Wednesday after callback window
SAT = "2026-10-17T11:00"
acct = {"last_act": "account", "r_ok": "true", "st": "account", "customer_id": "c1", "title": "Mr", "last_name": "Reyes",
        "p0_product_id": "p1", "p0_type": "credit_card", "p0_card_last4": "4821", "p0_past_due": 300, "p0_days_late": 3, "p0_minimum_payment": 50,
        "p1_product_id": "p2", "p1_type": "personal_loan", "p1_past_due": 400, "p1_days_late": 20, "p1_instalment_amount": 120}

def P(now, **over):
    # hand-computed state for Friday 16 Oct: early deadline 12 bd -> 2026-11-04 (26 Oct holiday), late 7 bd -> 2026-10-28
    base = [
        {"pid": "p1", "type": "credit_card", "card_last4": "4821", "full": 300.0, "dl": 3, "band": "early", "deadline": "2026-11-04", "att": 1, "used": 0, "floor": 50.0,
         "status": "open", "amount": None, "date": None, "too_much": False, "floor_offered": False, "vague": False, "pend": None, "fails": 0, "reason": ""},
        {"pid": "p2", "type": "personal_loan", "card_last4": None, "full": 400.0, "dl": 20, "band": "late", "deadline": "2026-10-28", "att": 2, "used": 0, "floor": 120.0,
         "status": "open", "amount": None, "date": None, "too_much": False, "floor_offered": False, "vague": False, "pend": None, "fails": 0, "reason": ""}]
    return json.dumps(base)

def S(name, rules, vars, expect):
    v = {"now": FRI, "customer_id": "c1", "title": "Mr", "last_name": "Reyes"}; v.update(vars)
    return {"name": name, "rules": rules, "run": ["step"], "vars": v, "expect": expect}

sc = [
    S("account facts two products, Friday", [2, 3, 16, 17, 18, 25], dict(acct),
      {"P": {"contains": "2026-11-04"}, "say": {"contains": "Can you pay all of them today?"}, "st": "today"}),
    S("account late deadline", [3, 18], dict(acct), {"P": {"contains": "2026-10-28"}}),
    S("account statement wording", [17, 2], dict(acct), {"say": {"contains": "credit card ending 4821 is 300 past due, 3 days late"}}),
    S("no today -> attempt 1 on product 1, next Friday since today is Friday", [4, 28, 30], {"st": "today", "P": P(FRI), "yesno": "no"},
      {"say": {"contains": "300 for your credit card ending 4821 on"}, "pi": "0", "P": {"contains": "2026-10-23"}}),
    S("one date for all after late deadline -> loan capped", [6, 23], {"st": "today", "P": P(FRI), "date_words": "on the 3rd of November", "yesno": "no"},
      {"say": {"contains": "the latest date I can record"}, "P": {"contains": "\"capped\": true"}}),
    S("plan label + future date -> promise check", [29, 41], {"st": "today", "P": P(FRI), "intent": "other", "date_words": "next Friday"},
      {"say": {"contains": "To confirm"}, "act": "talk"}),
    S("yes today -> read back all", [7, 34], {"st": "today", "P": P(FRI), "yesno": "yes"}, {"say": {"contains": "Do you confirm?"}, "st": "readback"}),
    S("too much -> floor once", [26], {"st": "prod", "pi": 0, "P": P(FRI), "intent": "too_much"}, {"say": {"contains": "minimum of 50"}}),
    S("below floor -> cannot record", [27], {"st": "prod", "pi": 0, "P": P(FRI), "amount_words": "twenty"}, {"say": {"contains": "cannot record less than 50"}}),
    S("weekend date -> next business day", [20, 19], {"st": "prod", "pi": 0, "P": P(FRI), "date_words": "Saturday"}, {"say": {"contains": "not a business day"}}),
    S("holiday date 26 Oct -> next business day 27 Oct", [20], {"st": "prod", "pi": 0, "P": P(FRI), "date_words": "2026-10-26"}, {"P": {"contains": "2026-10-27"}}),
    S("vague date asks once", [21], {"st": "prod", "pi": 0, "P": P(FRI), "date_words": "end of the month"}, {"say": {"contains": "exact day"}}),
    S("restructuring transfers", [10, 41], {"st": "prod", "pi": 0, "P": P(FRI), "intent": "restructure"}, {"act": "transfer", "v_queue": "restructuring"}),
    S("transfer result closes transferred", [10], {"last_act": "transfer", "r_ok": "true", "v_queue": "restructuring", "P": P(FRI), "st": "prod"},
      {"outcome": "transferred", "reason": "restructuring"}),
    S("paid on product 1 continues", [9, 39], {"st": "prod", "pi": 0, "P": P(FRI), "intent": "paid"}, {"say": {"contains": "one business day"}, "pi": "1"}),
    S("hardship offers support", [32], {"st": "prod", "pi": 0, "P": P(FRI), "intent": "hardship"}, {"say": {"contains": "customer support team"}}),
    S("human asked once", [42], {"st": "prod", "pi": 0, "P": P(FRI), "intent": "human"}, {"say": {"contains": "help you"}}),
    S("human second time transfer general", [42], {"st": "prod", "pi": 0, "P": P(FRI), "intent": "human", "human_asked": "yes"}, {"v_queue": "general", "act": "transfer"}),
    S("opening yes -> dob", [2, 3, 11], {"st": "confirm", "yesno": "yes"}, {"say": {"contains": "date of birth"}, "st": "dob"}),
    S("opening robot + unclear", [4], {"st": "confirm", "intent": "robot"}, {"say": {"contains": "digital assistant"}}),
    S("unclear twice -> not reached", [3], {"st": "confirm", "asks": 2}, {"outcome": "not_reached", "reason": "unclear"}),
    S("someone else + question -> third party", [5], {"st": "confirm", "yesno": "no", "intent": "question_what"}, {"st": "third"}),
    S("callback tomorrow=Saturday from Friday refused", [7], {"st": "third", "date_words": "tomorrow", "time_words": "11"}, {"say": {"contains": "another time"}}),
    S("wrong number", [8], {"st": "confirm", "intent": "wrong_number"}, {"outcome": "not_reached", "reason": "wrong_number"}),
    S("deceased", [9], {"st": "confirm", "intent": "deceased"}, {"say": {"contains": "I am sorry for your loss."}, "reason": "deceased"}),
    S("callback Monday 11 from Friday", [6], {"st": "third", "date_words": "Monday", "time_words": "eleven in the morning"}, {"act": "callback", "cb_time": "11:00", "cb_date": "2026-10-19"}),
    S("callback after window", [7], {"st": "third", "now": LATE, "date_words": "today", "time_words": "8 pm"}, {"say": {"contains": "another time"}}),
    S("callback 19:00 edge, day before holiday", [6], {"st": "third", "now": PRE_HOL, "date_words": "today", "time_words": "19:00"}, {"act": "callback", "cb_date": "2026-10-23"}),
    S("callback saturday -> next bd monday", [6], {"st": "third", "now": SAT, "date_words": "Monday", "time_words": "10:00"}, {"act": "callback", "cb_date": "2026-10-19"}),
    S("dob full words", [11], {"st": "dob", "dob_words": "fifth of March 1985"}, {"v_answer": "1985-03-05", "act": "verify"}),
    S("dob numeric day first", [11], {"st": "dob", "dob_words": "05/03/1985"}, {"v_answer": "1985-03-05"}),
    S("dob partial asks year", [11], {"st": "dob", "dob_words": "March fifth"}, {"say": {"contains": "year"}}),
    S("wrong answer third -> failed", [12, 14], {"last_act": "verify", "r_ok": "true", "r_verified": "false", "wrong": 2, "v_field": "phone_last4", "st": "phone"}, {"outcome": "not_verified", "reason": "failed"}),
    S("swap hint not counted", [13], {"last_act": "verify", "r_ok": "true", "r_verified": "false", "r_hint": "day_month_swapped", "v_field": "date_of_birth", "st": "dob"}, {"say": {"contains": "month as a word"}}),
    S("decline twice before verification", [15, 45], {"st": "dob", "intent": "question_what", "dq": 1}, {"outcome": "not_verified", "reason": "declined"}),
    S("phone digits in pieces", [11], {"st": "phone", "digits": "four eight", "digs": ""}, {"digs": "48"}),
    S("confirm read back -> promise call", [7, 34], {"st": "readback", "yesno": "yes", "P": P(FRI).replace('"status": "open", "amount": null, "date": null', '"status": "agreed", "amount": 300, "date": "2026-10-20"', 1)},
      {"act": "promise", "v_pid": "p1"}),
    S("promise fails twice -> note service_error", [11, 37], {"last_act": "promise", "r_ok": "false", "rec_i": 0, "st": "recording",
      "P": P(FRI).replace('"status": "open"', '"status": "confirmed"', 1).replace('"fails": 0', '"fails": 1', 1)}, {"act": "note", "v_reason": "service_error", "v_pid": "p1"}),
    S("all refused -> notes then close no_promise refused", [8, 31], {"st": "recording", "P": P(FRI).replace('"status": "open"', '"status": "noted"').replace('"reason": ""', '"reason": "refused"').replace('"fails": 0', '"fails": 0, "noted": true')},
      {"outcome": "no_promise", "reason": "refused"}),
    S("all paid -> paid", [39], {"st": "recording", "P": P(FRI).replace('"status": "open"', '"status": "noted"').replace('"reason": ""', '"reason": "paid"').replace('"fails": 0', '"fails": 0, "noted": true')},
      {"outcome": "paid"}),
    S("one recorded -> promise + sms", [38, 46, 47], {"st": "recording", "P": P(FRI).replace('"status": "open"', '"status": "recorded"', 1).replace('"status": "open"', '"status": "noted"').replace('"reason": ""', '"reason": "refused"').replace('"fails": 0', '"fails": 0, "noted": true')},
      {"outcome": "promise", "say": {"contains": "text message confirming"}}),
    S("attempt 2 late band floor on deadline", [5, 30], {"st": "prod", "pi": 1, "P": P(FRI).replace('"used": 0, "floor": 120.0', '"used": 1, "floor": 120.0'), "yesno": "no"},
      {"say": {"contains": "120 for your personal loan on"}, "P": {"contains": "2026-10-28"}}),
    S("discount answered", [33, 44], {"st": "prod", "pi": 0, "P": P(FRI), "intent": "discount"}, {"say": {"contains": "cannot offer a discount"}}),
    S("scam answered", [43], {"st": "confirm", "intent": "scam"}, {"say": {"contains": "customer service number"}}),
    S("change recorded promise -> app", [36, 35], {"st": "prod", "pi": 0, "P": P(FRI), "intent": "changes_promise"}, {"say": {"contains": "mobile app"}}),
    S("dispute product 1 continues", [40, 9], {"st": "prod", "pi": 0, "P": P(FRI), "intent": "dispute"}, {"P": {"contains": "\"reason\": \"dispute\""}}),
]
json.dump(sc, open("out/scenarios.json", "w"), indent=1)
cov = {}
import re
for line in open("inputs/related/brief-a.md").read().splitlines() + open("inputs/brief-b.md").read().splitlines():
    m = re.match(r"^(\d+)\. ", line)
    if m: cov[m.group(1)] = "step node code (out/step_body.py)"
cov.update({"1": "opening node on_enter", "2": "opening node on_enter; step account facts", "46": "close_call workflow tool alwaysRunsAt end_of_call + close_pre_process",
            "47": "close(): goodbye in goodbye end_call spoken_message", "33": "talk task_message + discount intent sentence", "10": "transfer(); next_record skips notes after transfer",
            "44": "wording: talk node says only the given text"})
json.dump(cov, open("out/coverage.json", "w"), indent=1)
