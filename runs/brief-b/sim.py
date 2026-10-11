import json, sys
wf = json.load(open("out/brief-b.workflow.json"))
CODE = wf["nodes"]["brain"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]
PRODS = [{"product_id": "p1", "type": "credit_card", "card_last4": "4821", "past_due": 300, "days_late": 5, "minimum_payment": 50},
         {"product_id": "p2", "type": "personal_loan", "past_due": 400, "days_late": 20, "instalment_amount": 200}]
def run(now, turns, prods=PRODS, fail=()):
    v = {"now": now, "title": "Mr", "last_name": "Reyes", "customer_id": "c1"}
    calls = []; ti = 0
    def step():
        exec(CODE, {"vars": v})
    step()
    for _ in range(80):
        a = v["act"]
        if a == "end": print("  BOT(end):", v["say"]); break
        if a == "talk":
            print("  BOT:", v["say"])
            if ti >= len(turns): print("  (out of turns)"); break
            u = turns[ti]; ti += 1; print("  USER:", u); v.update(u); step(); continue
        calls.append(a); v["r_ok"] = "false" if a in fail and calls.count(a) <= 2 else True
        if a in fail: v["r_ok"] = ""
        if a == "verify": v["r_verified"] = True; v["r_all"] = v["v_field"] == "phone_last4"; calls[-1] += ":" + v["v_answer"]
        if a == "account":
            for i, p in enumerate(prods):
                for k, x in p.items(): v["do_account_response.data.products.%d.%s" % (i, k)] = x
        if a == "promise": calls[-1] += ":%s/%s/%s" % (v["a_pid"], v["a_amount"], v["a_date"])
        if a == "note": calls[-1] += ":%s/%s" % (v["a_pid"], v["a_reason"])
        if a == "transfer": calls[-1] += ":" + v["a_queue"]
        if a == "callback": calls[-1] += ":%s %s" % (v["a_date"], v["a_time"])
        step()
    print("  CALLS:", calls, "CLOSE:", v.get("outcome"), v.get("reason"), v.get("dbg", ""))
ID = [{"intent": "yes"}, {"dob_day": 15, "dob_month": 3}, {"dob_year": 1985}, {"digits": "48"}, {"digits": "21"}]
sc = {
 "all today": ID + [{"intent": "yes"}, {"intent": "yes"}],
 "one date both (Wed 14 Oct, next Friday=23rd > late deadline?)": ID + [{"intent": "no", "date_words": "the 28th"}, {"intent": "yes"}],
 "refuse all": ID + [{"intent": "no"}, {"intent": "no"}, {"intent": "no"}, {"intent": "no"}, {"intent": "no"}],
 "card paid, loan dispute": ID + [{"intent": "paid"}, {"intent": "dispute"}],
 "plan with date": ID + [{"intent": "plan", "date_words": "Friday"}],
 "card promise then plan": ID + [{"intent": "no"}, {"intent": "yes"}, {"intent": "plan"}],
 "hardship decline": ID + [{"intent": "hardship"}, {"intent": "no"}],
 "too much": ID + [{"intent": "too_much"}, {"intent": "yes"}, {"amount": 100}, {"amount": 200, "date_words": "tomorrow"}, {"intent": "yes"}],
 "third party callback": [{"intent": "no", "time_words": "3 pm", "date_words": "tomorrow"}],
 "third party bad twice": [{"intent": "no"}, {"time_words": "9 pm"}, {"time_words": "8 am"}],
 "human twice in identity": [{"intent": "yes"}, {"intent": "human"}, {"intent": "human"}],
 "declined id": [{"intent": "yes"}, {"intent": "what_about"}, {"intent": "refuse_talk"}],
 "unclear": [{"intent": "none"}, {"intent": "none"}],
 "robot then yes": [{"intent": "robot"}, {"intent": "yes"}, {"intent": "human"}, {"intent": "human"}],
}
for k, t in sc.items():
    print("==", k); run(sys.argv[1] if len(sys.argv) > 1 else "2026-10-14T11:00", t)
print("== promise fail"); run("2026-10-14T11:00", ID + [{"intent": "yes"}, {"intent": "yes"}], fail=("promise",))
