import json, sys
sys.path.insert(0, "lib")
from snippets import code
SPEC = json.load(open("out/spec.json"))
API = json.load(open("inputs/openapi.json"))
BASE = API["servers"][0]["url"]
SLOT = "brief-a-mutant"
CSPEC = json.loads(json.dumps(SPEC)); CSPEC["sentences"].pop("opening"); CSPEC.pop("unclear_notes")
BODY = open("out/step_body.py").read()
assert "{{" not in BODY and "}}" not in BODY
HDR = {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}}

def always(t): return {"target_node": t, "description": "always", "condition": {"operator": "always"}}
def eq(var, val): return {"logic": "or", "conditions": [{"variable": var, "operator": "equals", "operand": val}]}

def api_body(path, fields):
    schema = API["paths"]["/" + path]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]
    props = {}
    for f, default in fields.items():
        leaf = {k: v for k, v in schema[f].items() if k in ("type", "enum", "description")}
        leaf["default"] = default
        props[f] = leaf
    return {"type": "object", "properties": props, "required": []}

def api_node(name, path, fields, mapping):
    return {"name": name, "node_type": "api_request", "passthrough": True, "passthrough_default_transition": "step",
            "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
            "pre_actions": [{"type": "function", "config": {"timeoutMs": 12000, "maxRetries": 0},
                "function": {"name": path, "handler": "__function__:api_call", "description": path,
                    "parameters": {"type": "object", "properties": {"url": {"type": "string", "default": BASE + "/" + path},
                        "method": {"type": "string", "default": "POST"}, "headers": HDR, "body": api_body(path, fields)}}}}],
            "response_mapping": [{"path": "data." + p, "variable": v} for p, v in mapping],
            "transitions": [always("step")]}

INTENTS = [
 ("agree", "clear yes: yes, that's me, speaking, I confirm, I can pay, okay"),
 ("decline", "a plain no or refusal of the payment or of the offer, with no date and no amount"),
 ("other_person", "someone other than the customer answers (not him or her, a relative, colleague, 'he is not here')"),
 ("wrong_number", "says the number does not belong to the customer / wrong number"),
 ("deceased", "says the customer has died"),
 ("robot_question", "asks whether the speaker is a robot, machine or AI"),
 ("scam_question", "asks whether this is a scam or fraud"),
 ("what_about", "asks who is calling or what the call is about or why, instead of answering"),
 ("other_question", "asks any other question"),
 ("human", "asks for a human, a person or an agent"),
 ("refuse_talk", "says they do not want to talk, are not interested, or refuses to answer the security questions"),
 ("paid", "says they already paid this amount"),
 ("dispute", "says the debt is not theirs, they never had the product, or it was closed or paid off in the past"),
 ("restructure", "asks for a new payment plan or lower instalments"),
 ("hardship", "mentions illness, a death in the family or job loss"),
 ("full_too_much", "says the full amount is too much but names no amount"),
 ("terms_request", "asks for a discount, a waiver, a lower price or any other term"),
 ("none", "none of the above, a greeting such as hello, or unclear")]
SCHEMA = [
 {"name": "intent", "type": "string", "enum_values": [i for i, _ in INTENTS], "min_confidence": 0.6,
  "description": "What the customer's last message is. Values: " + "; ".join(i + " = " + d for i, d in INTENTS) + ". Use none when unsure."},
 {"name": "date_words", "type": "string", "min_confidence": 0.6, "description": "The day the customer names for a payment or a callback, in their own words (tomorrow, the 20th, next Friday, end of the month). Empty if none."},
 {"name": "time_words", "type": "string", "min_confidence": 0.6, "description": "A clock time the customer names, in their words (eleven in the morning, 3 pm). Empty if none."},
 {"name": "amount_words", "type": "string", "min_confidence": 0.6, "description": "An amount of money the customer says they can pay, digits only, e.g. 250 or 250.50. Empty if none."},
 {"name": "dob_text", "type": "string", "min_confidence": 0.6, "description": "A date of birth or a part of it, written with digits and the month name as the customer said it, e.g. '14 March 1985', 'March' or '1985'. Numbers only like 03/04/1985 stay as said. Empty if none."},
 {"name": "digits_text", "type": "string", "min_confidence": 0.6, "description": "Digits the customer says as phone digits, as digits only. Empty if none."}]

def conv(name, on_enter, task):
    return {"name": name, "node_type": "conversation", "on_enter": on_enter, "task_message": task,
            "extraction_schema": SCHEMA, "max_node_turns": 6, "max_turn_transition": "step", "transitions": [always("step")]}

TASK = "Say the following to the customer in one or two short sentences. Keep every number, date, name and quoted sentence exactly as written. Add nothing else. Do not call any tool.\nText: {{say}}"
nodes = {}
nodes["opening"] = conv("opening", {"type": "tts", "text": SPEC["sentences"]["opening"]},
                        "Wait for the customer's answer. Do not call any tool.")
nodes["talk"] = conv("talk", {"type": "llm"}, TASK)
nodes["talk"]["max_node_turns"] = 6
nodes["step"] = {"name": "step", "node_type": "code", "passthrough": True, "passthrough_default_transition": "talk",
    "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
    "pre_actions": [{"type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec",
        "parameters": {"type": "object", "properties": {"code": {"type": "string", "default": code(BODY, CSPEC)}, "timeout_ms": {"type": "number", "default": 10000}}}}}],
    "transitions": [{"target_node": t, "description": n, "condition": eq("next_node", n)} for n, t in
        [("verify", "verify_api"), ("account", "account_api"), ("promise", "promise_api"), ("callback", "callback_api"), ("transfer", "transfer_api"), ("end", "goodbye")]] + [always("talk")]}
CID = "{{customer_id}}"
nodes["verify_api"] = api_node("verify_api", "verify_identity", {"customer_id": CID, "field": "{{v_field}}", "answer": "{{v_answer}}"},
    [("ok", "v_ok"), ("verified", "v_verified"), ("wrong_answers_left", "v_left"), ("all_verified", "v_all"), ("hint", "v_hint")])
nodes["account_api"] = api_node("account_api", "get_account", {"customer_id": CID}, [("ok", "a_ok"), ("products", "products")])
nodes["promise_api"] = api_node("promise_api", "create_promise", {"customer_id": CID, "product_id": "{{p_id}}", "amount": "{{cur_amt}}", "date": "{{cur_date}}"}, [("ok", "pr_ok")])
nodes["callback_api"] = api_node("callback_api", "schedule_callback", {"customer_id": CID, "date": "{{cb_date}}", "time": "{{cb_time}}"}, [("ok", "cb_ok")])
nodes["transfer_api"] = api_node("transfer_api", "transfer_to_agent", {"customer_id": CID, "queue": "{{queue}}"}, [("ok", "tr_ok")])
# api_node default resets for stale results are written by code; account/promise/callback results reset here via names
nodes["goodbye"] = {"name": "goodbye", "node_type": "end_call", "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True, "transitions": [],
    "terminal": {"type": "function", "function": {"name": "call_end", "handler": "__function__:end_call",
        "parameters": {"type": "object", "properties": {"message_mode": {"type": "string", "default": "custom"}, "spoken_message": {"type": "string", "default": "{{closing_say}}"}}}}}}
close_tool = {"type": "function", "config": {"timeoutMs": 12000, "maxRetries": 0, "alwaysRunsAt": ["end_of_call"]},
  "function": {"name": "close_call", "handler": "__function__:api_call", "description": "Record how the call ended.",
    "parameters": {"type": "object", "properties": {"url": {"type": "string", "default": BASE + "/close_call"}, "method": {"type": "string", "default": "POST"}, "headers": HDR,
      "body": api_body("close_call", {"customer_id": CID, "outcome": "{{outcome}}", "reason": "{{reason}}"})}}},
  "pre_process_code": "try:\n    b = config.get('body')\n    if isinstance(b, dict) and b.get('outcome') in ('promise', 'paid'):\n        b.pop('reason', None)\nexcept Exception:\n    pass\n"}
wf = {"initial_node": "opening",
  "system_prompt": "You are the digital assistant of Freya Bank on a phone call. Speak English, one or two short sentences per turn. Say only what you are told to say. Never offer a discount, waiver, instalment plan or any term. A recorded promise cannot be changed in this call; the customer can change it in the mobile app.",
  "nodes": nodes, "global_nodes": {}, "tools": [close_tool],
  "test_variables": {"customer_id": "c_test", "first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"}}
json.dump(wf, open("out/%s.workflow.json" % SLOT, "w"), indent=1)
