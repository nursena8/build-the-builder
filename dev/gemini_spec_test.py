"""One-off test: can Gemini extract a complete spec from briefs/brief-a.md + tools/openapi.json?

    source env.sh && python3 dev/gemini_spec_test.py gemini-3.8-flash low dev/spec-a-flash.json

Standard library only. Reads GEMINI_API_KEY from the environment. One generateContent call per run.
Logs only metadata (model, seconds, usage) to dev/llm-calls.jsonl, never the prompt or the key.
"""
import json, os, pathlib, sys, time, urllib.error, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = "https://generativelanguage.googleapis.com/v1beta/models/"

SECTIONS = """Return ONE JSON object with these top-level keys (use exactly these names):
call_variables, opening, identity, third_party, calendar, bands, amounts, promise_taking, other_intents,
outcome_table, closing_and_tone, tool_mapping.

What each key must hold:
- call_variables: the variables every call starts with and how to address the customer.
- opening: required elements of the first sentence, words forbidden before identity is verified, the confirmation rule for "who is on the line".
- identity: the list of security questions in the order they are asked (field name, answer format, conversion rule), wrong-answer limit, special retry rules (such as the day/month swap), refusal flow, the outcome on failure and on refusal.
- third_party: what may and may not be said, callback window (days, hours, inclusive or not, later than now), wrong number, deceased, what a relative may do.
- calendar: business-day definition, holiday list, rules for "next <weekday>" and "this <weekday>".
- bands: thresholds, deadline expressed in business days, number of persuasion attempts and what each attempt proposes.
- amounts: floor rule per product type, accepted amount range, order of offers, prohibitions.
- promise_taking: read-back, confirmation, recording, retry on failure, what to say after a recorded promise.
- other_intents: already paid, dispute, payment plan, human, scam question, unknown question, unwillingness counter.
- outcome_table: every outcome with its reasons and the rule that triggers it.
- closing_and_tone: goodbye and tone rules, tool-order rules.
- tool_mapping: for each tool from the OpenAPI file, its fields and every enum value, copied exactly.

Rules for the content:
- Every entry in every section is an object with a "text" field and a "rules" field. "rules" lists the rule numbers of the brief that the entry comes from, as integers.
- Add nothing that is not in the sources. If you are not sure, set "unclear": true on that entry.
- Copy numbers, dates, times and names exactly. Do not round or reinterpret.
- Output JSON only."""


def call_gemini(model, prompt, thinking_level, max_out=32768, timeout=420):
    key = os.environ["GEMINI_API_KEY"]
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": max_out,
                                 "thinkingConfig": {"thinkingLevel": thinking_level}}}
    req = urllib.request.Request(BASE + model + ":generateContent", data=json.dumps(body).encode(),
                                 headers={"x-goog-api-key": key, "Content-Type": "application/json"}, method="POST")
    t0 = time.time(); status = "ok"; out = {}
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: out = json.load(r)
    except urllib.error.HTTPError as e:
        status = "http_%d" % e.code; err = e.read().decode()[:800].replace(key, "***")
        out = {"error": err}
    dt = time.time() - t0
    meta = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "model": model, "thinking_level": thinking_level, "seconds": round(dt, 1),
            "status": status, "usage": out.get("usageMetadata"), "finish": (out.get("candidates") or [{}])[0].get("finishReason")}
    with open(ROOT / "dev" / "llm-calls.jsonl", "a") as f: f.write(json.dumps(meta) + "\n")
    return out, meta


if __name__ == "__main__":
    model, level, dest = sys.argv[1], sys.argv[2], sys.argv[3]
    prompt = ("You read a bank's collections brief and the bank's tool API, and you write a structured spec.\n\n"
              + SECTIONS + "\n\n=== BRIEF ===\n" + (ROOT / "briefs" / "brief-a.md").read_text()
              + "\n\n=== TOOL API (OpenAPI) ===\n" + (ROOT / "tools" / "openapi.json").read_text())
    out, meta = call_gemini(model, prompt, level)
    print(json.dumps(meta))
    if meta["status"] != "ok":
        print(out.get("error")); sys.exit(1)
    text = "".join(p.get("text", "") for p in out["candidates"][0]["content"].get("parts", []))
    pathlib.Path(dest).write_text(text)
    try: json.loads(text); print("gecerli JSON,", len(text), "karakter")
    except Exception as e: print("JSON PARSE HATASI:", e, "| karakter:", len(text))
