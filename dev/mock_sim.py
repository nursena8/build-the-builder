"""Dress rehearsal against OUR mock: two Turkish customers talk to an agent in a Freya simulation, the tools hit the mock, the ledger is read from the mock.

    source env.sh && python3 dev/mock_sim.py <agent_id> <mock_url>

Needs the demo customers of mock/customers.mjs (c_demo_1, c_demo_2) in the deployed mock. Resets them first. One simulation, about 3 minutes."""
import json, os, pathlib, sys, time, urllib.request
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); import freya

agent, mock = sys.argv[1], sys.argv[2].rstrip("/")
H = {"content-type": "application/json", "user-agent": "Mozilla/5.0 (rehearsal)", "x-admin-key": "change-me"}
def req(path, body=None):
    r = urllib.request.Request(mock + "/v1" + path, data=json.dumps(body).encode() if body is not None else None, headers=H, method="POST" if body is not None else "GET")
    return json.load(urllib.request.urlopen(r, timeout=30))

RULES = ("OUTPUT RULE: you speak only Turkish. Write only the words you say on the phone, one or two short sentences per turn, then wait. Say numbers and dates the way a Turkish speaker "
         "says them, in words. Answer only what you are asked. When the caller reads something back and it matches, say 'Evet, onaylıyorum.' When the caller says goodbye, say 'Teşekkürler, hoşça kalın.'")
CUSTOMERS = [
  ("c_demo_1", "Daniel", "Reyes", "Mr", f"{RULES}\nYou are Daniel Reyes. Your date of birth is 14 March 1988 and the last four digits of your phone are 2219 (give them only when asked). "
   "When told about the late payment you cannot pay today but you can pay the full amount on 'haftaya cuma'.",
   "The agent speaks Turkish. A promise for the full amount on Friday 23 October 2026 is recorded in the bank's records. The agent never says it is recorded before the tool succeeded."),
  ("c_demo_2", "Grace", "Lin", "Ms", f"{RULES}\nYou are Grace Lin. Your date of birth is 23 February 1989 and the last four digits of your phone are 9904 (give them only when asked). "
   "When told about the late payment you cannot pay today, but you can pay the full amount this Friday (bu cuma).",
   "The agent speaks Turkish. A promise for the full amount on Friday 16 October 2026 is recorded in the bank's records, even though the first attempt to record it failed. The agent does not say it is recorded after the failure."),
]
for cid, *_ in CUSTOMERS: req("/admin/reset", {"customer_id": cid})
personas = freya.create_personas([{"name": f"mock rehearsal {cid} {int(time.time())}", "prompt": p, "successCriteria": crit, "tags": ["rehearsal"]} for cid, f, l, t, p, crit in CUSTOMERS])["personas"]
vars_by = {pe["id"]: {"customer_id": c[0], "first_name": c[1], "last_name": c[2], "title": c[3], "now": "2026-10-14T11:00"} for pe, c in zip(personas, CUSTOMERS)}
t0 = time.time(); sim, it, status = freya.run_simulation(agent, f"mock rehearsal {time.strftime('%H:%M:%S')}", vars_by)
print(f"simulation {sim} {status} in {time.time() - t0:.0f} s")
judge = {r["personaId"]: r for r in freya.get_iteration(sim, it)["runs"]}
for pe, c in zip(personas, CUSTOMERS):
    led = req("/ledger/" + c[0]); j = judge.get(pe["id"], {})
    print(f"\n== {c[0]}: judge {j.get('outcome')} | bank: outcome={led['outcome']}/{led['reason']} promises={led['promises']} tools={[x['tool'] for x in led['calls']]}")
    print("   judge:", " ".join(str(j.get("reason") or "").split())[:300])
