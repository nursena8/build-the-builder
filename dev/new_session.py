"""Print a fresh practice session for a manual text call: the call variables to paste, and what the customer knows.

    source env.sh && python3 dev/new_session.py PUB-01

Only PUB ids. A session is single use: the call's close_call burns it, so make a new one for each manual call.
"""
import json, os, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools")); from score import http
cid = sys.argv[1]
case = next(c for c in json.load(open(ROOT / "public-test-set.json")) if c["id"] == cid)
v = http("/v1/practice/sessions", {"case": cid})["variables"]
print("Paste these call variables:\n" + json.dumps(v, indent=1))
print("\nThe customer is " + v["title"] + " " + v["last_name"] + ".")
print("Date of birth:", case["identity"]["date_of_birth"], "| phone last 4:", case["identity"]["phone_last4"])
for i, p in enumerate(case["products"], 1):
    print(f"p{i}:", json.dumps(p))
