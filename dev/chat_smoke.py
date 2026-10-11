"""Live smoke test through the chat API: one Turkish customer talks to a workflow, turn by turn. No simulation slot needed.

    source env.sh && python3 dev/chat_smoke.py <workflow_id> [PUB-01] [dob_words|digits]

Uses a fresh practice session (single use: close_call burns it). Prints each turn and the bank's ledger at the end.
Customer lines are Turkish; the identity answers come from the practice case, said the way a person says them."""
import json, os, pathlib, sys, time, urllib.request
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
import freya
from score import http

W = ["sıfır", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
MON = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

def turn(wid, msg, call_id, variables):
    body = {"workflowId": wid, "message": msg}
    if call_id: body["callId"] = call_id
    else: body["customerVariables"] = variables
    for i in range(3):
        try: return freya.api("POST", "/api/v2/chat/message", body)
        except Exception as e:
            print("   (retry)", str(e)[:120]); time.sleep(5)
    raise SystemExit("chat failed")

def main():
    wid = sys.argv[1]; cid = sys.argv[2] if len(sys.argv) > 2 else "PUB-01"
    case = next(c for c in json.load(open(ROOT / "public-test-set.json")) if c["id"] == cid)
    v = http("/v1/practice/sessions", {"case": cid})["variables"]
    y, m, d = case["identity"]["date_of_birth"].split("-")
    dob = f"{int(d)} {MON[int(m)]} {y}"
    last4 = " ".join(W[int(c)] for c in case["identity"]["phone_last4"])
    lines = ["Evet, benim.", f"Doğum tarihim {dob}.", last4, "Bugün ödeyemem ama haftaya cuma ödeyebilirim.", "Evet, onaylıyorum."]
    call_id = None
    for line in [None] + lines:
        r = turn(wid, line or "Alo?", call_id, v)
        res = r.get("result") or r.get("data") or r
        call_id = res.get("callId") or call_id
        print(f"MÜŞTERİ: {line}" if line else "MÜŞTERİ: (arama açılır)"); print("AGENT  :", res.get("response"))
    try: freya.api("POST", "/api/v2/chat/end", {"callId": call_id})
    except Exception as e: print("end:", str(e)[:100])
    print(json.dumps(http("/v1/practice/ledger/" + v["customer_id"]), ensure_ascii=False)[:900])
main()
