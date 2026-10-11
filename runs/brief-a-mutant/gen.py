import json, sys, pathlib
sys.path.insert(0, "lib")
import snippets
from snippets import code

ROOT = pathlib.Path(__file__).resolve().parent.parent
SLOT = "brief-a-mutant"
spec_raw = json.load(open(ROOT / "out/spec.json"))
SPEC = {k: v["value"] for k, v in spec_raw.items()}
api = json.load(open(ROOT / "inputs/openapi.json"))
BASE = api["servers"][0]["url"].rstrip("/")
PATHS = api["paths"]


def url(op):
    assert "/" + op in PATHS
    return BASE + "/" + op


def props(op):
    return PATHS["/" + op]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]


def api_fn(name, op, body):
    p = props(op)
    bp = {}
    for k, default in body.items():
        leaf = {"type": p[k].get("type", "string"), "default": default}
        if "enum" in p[k]: leaf["enum"] = p[k]["enum"]
        bp[k] = leaf
    return {"type": "function", "config": {"timeoutMs": 12000, "maxRetries": 0},
            "function": {"name": name, "handler": "__function__:api_call", "description": PATHS["/" + op]["post"]["summary"],
                         "parameters": {"type": "object", "properties": {
                             "url": {"type": "string", "default": url(op)},
                             "method": {"type": "string", "default": "POST"},
                             "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                             "body": {"type": "object", "properties": bp, "required": list(bp.keys())}}}}}


def code_fn(src):
    while "}}" in src or "{{" in src:
        src = src.replace("}}", "} }").replace("{{", "{ {")
    assert "{{" not in src and "}}" not in src, "braces in code"
    return {"type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec",
            "parameters": {"type": "object", "properties": {"code": {"type": "string", "default": src}, "timeout_ms": {"type": "number", "default": 20000}}}}}


def always(t):
    return {"target_node": t, "description": "always", "condition": {"operator": "always"}}


def eq(var, val, t):
    return {"target_node": t, "description": "%s is %s" % (var, val),
            "condition": {"logic": "or", "conditions": [{"variable": var, "operator": "equals", "operand": val}]}}


def passnode(name, ntype, pre, nxt, mapping=None, transitions=None):
    n = {"name": name, "node_type": ntype, "passthrough": True, "passthrough_default_transition": nxt,
         "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True, "pre_actions": pre,
         "transitions": (transitions or []) + [always(nxt)]}
    if mapping: n["response_mapping"] = mapping
    return n


S = SPEC["say"]
EXTR_NONE = ["who", "question", "intent", "answer", "date_words", "time_words", "amount_said", "dob_day", "dob_month", "dob_year", "phone_digits"]

init_body = (
    "vars['st'] = 'who'\nvars['who_asks'] = 1\nvars['loops'] = 0\nvars['pending'] = 'none'\nvars['next'] = 'talk'\n"
    "vars['outcome'] = ''\nvars['reason'] = ''\nvars['promised'] = 'no'\nvars['bye'] = %r\n"
    "vars['say'] = %r + ' Am I speaking with ' + str(vars.get('title') or '') + ' ' + str(vars.get('last_name') or '') + '?'\n"
    "for k in %r:\n    vars[k] = 'none'\n" % (S["goodbye"], S["opening"], EXTR_NONE))

brain_body = (ROOT / "out/brain.py").read_text()
step_spec = {k: SPEC[k] for k in ["holidays", "weekend", "bands", "floor_fields", "next_week_mode", "callback_window",
                                  "callback_out_of_window_asks", "who_asks_max", "wrong_answers_max", "decline_max",
                                  "stop_talking_max", "human_asks_before_transfer", "tool_retries", "queues", "outcomes", "say"]}


def ex(name, desc, enum=None):
    e = {"name": name, "type": "string", "description": desc, "min_confidence": 0.5}
    if enum: e["enum_values"] = enum
    return e


extraction = [
    ex("who", "Only from the customer's LAST message, about who is on the line. confirmed: says yes, that's me, speaking, or says the customer's own name. "
              "not_customer: says they are someone else (a relative, a partner, a colleague) or that the customer is not there/available. unclear: hello, go ahead, who is this, or anything else. none: not about who is speaking.",
       ["none", "confirmed", "not_customer", "unclear"]),
    ex("question", "A question in the LAST message. robot: asks if this is a robot or AI. scam: asks if this is a scam or a real call. "
                   "purpose: asks what the call is about or why we call. cannot_answer: any other question about facts (fees, interest, balance history, why the amount is this). none: no question.",
       ["none", "robot", "scam", "purpose", "cannot_answer"]),
    ex("intent", "What the LAST message does. paid: says they already paid this past-due amount. dispute: says the debt is not theirs, they never had the product, or it was closed or paid off in the past. "
                 "plan: explicitly asks for a new payment plan, instalments or lower instalments (naming a date is not a plan). hardship: mentions illness, a death in the family or job loss. "
                 "too_much: says the full amount is too much or they cannot afford all of it. discount: asks for a discount, waiver or lower price. human: asks for a human, a person, an agent. "
                 "stop_talking: says they do not want to talk / end this call. refuse: refuses to pay or refuses to answer the security question, with no date and no amount. "
                 "vague: gives a vague period (next week, end of the month, when my salary comes) without an exact day. accept: agrees to what was proposed. "
                 "wrong_number: says this number does not belong to the customer. deceased: says the customer has died. change_promise: wants to change or cancel a recorded promise. "
                 "incomplete: the message stops mid-sentence. other: anything else. none: nothing of these.",
       ["none", "paid", "dispute", "plan", "hardship", "too_much", "discount", "human", "stop_talking", "refuse", "vague", "accept", "wrong_number", "deceased", "change_promise", "incomplete", "other"]),
    ex("answer", "yes or no answer in the LAST message to the agent's last yes/no question (for example 'Can you make this payment today?', 'Do you confirm?', 'Could you pay X on Y?'). none if neither.",
       ["none", "yes", "no"]),
    ex("date_words", "The day the customer names in the LAST message as a future payment or callback day, copied in their own words (for example 'tomorrow', 'next Friday', 'this Friday', 'the 20th', 'October 23'). "
                     "Write none when no day is named, and none for a past payment date."),
    ex("time_words", "A clock time the customer names in the LAST message for a callback, in their words (for example 'eleven in the morning', '3 pm', '15:30'). none if no time."),
    ex("amount_said", "An amount of money the customer says in the LAST message they can pay, as a plain number like 120 or 75.50. none if no amount."),
    ex("dob_day", "Day of month of the customer's date of birth said in the LAST message, as digits (1-31). A date said only in numbers is day, then month, then year. none if not said."),
    ex("dob_month", "Month of the customer's date of birth said in the LAST message, as a number 1-12 (March is 3). A date said only in numbers is day, then month, then year. none if not said."),
    ex("dob_year", "Year of the customer's date of birth said in the LAST message, as four digits. none if not said."),
    ex("phone_digits", "Digits of the phone number the customer says in the LAST message, digits only (for example 4821). none if no digits."),
]

talk = {
    "name": "talk", "node_type": "conversation",
    "on_enter": {"type": "tts", "text": "{{say}}"},
    "task_message": "Say exactly this text: \"{{say}}\"\nSay exactly this text. Never promise a transfer, a callback or any other action that the text does not state. Do not call any tool.",
    "extraction_schema": extraction,
    "tools": [],
    "max_node_turns": 3, "max_turn_transition": "step",
    "transitions": [always("step")],
}

step_tr = [eq("next", "end", "end"), eq("next", "verify_identity", "verify_identity"), eq("next", "get_account", "get_account"),
           eq("next", "create_promise", "create_promise"), eq("next", "schedule_callback", "schedule_callback"), eq("next", "transfer_to_agent", "transfer_to_agent")]

nodes = {
    "init": passnode("init", "code", [code_fn(init_body)], "talk"),
    "talk": talk,
    "step": passnode("step", "code", [code_fn(code(brain_body, step_spec))], "talk", transitions=step_tr),
    "verify_identity": passnode("verify_identity", "api_request",
                           [api_fn("verify_identity", "verify_identity", {"customer_id": "{{customer_id}}", "field": "{{v_field}}", "answer": "{{v_answer}}"})], "step",
                           mapping=[{"path": "data.ok", "variable": "v_ok"}, {"path": "data.verified", "variable": "v_verified"},
                                    {"path": "data.all_verified", "variable": "v_all"}, {"path": "data.hint", "variable": "v_hint"},
                                    {"path": "data.wrong_answers_left", "variable": "v_left"}, {"path": "data.error", "variable": "v_error"}]),
    "get_account": passnode("get_account", "api_request", [api_fn("get_account", "get_account", {"customer_id": "{{customer_id}}"})], "step",
                            mapping=[{"path": "data.ok", "variable": "a_ok"}] + [
                                {"path": "data.products.0.%s" % f, "variable": "p0_%s" % f} for f in
                                ["product_id", "type", "card_last4", "past_due", "days_late", "minimum_payment", "instalment_amount"]]),
    "create_promise": passnode("create_promise", "api_request",
                            [api_fn("create_promise", "create_promise", {"customer_id": "{{customer_id}}", "product_id": "{{product_id}}", "amount": "{{p_amount}}", "date": "{{p_date}}"})], "step",
                            mapping=[{"path": "data.ok", "variable": "pr_ok"}]),
    "schedule_callback": passnode("schedule_callback", "api_request",
                             [api_fn("schedule_callback", "schedule_callback", {"customer_id": "{{customer_id}}", "date": "{{cb_date}}", "time": "{{cb_time}}"})], "step",
                             mapping=[{"path": "data.ok", "variable": "cb_ok"}]),
    "transfer_to_agent": passnode("transfer_to_agent", "api_request",
                             [api_fn("transfer_to_agent", "transfer_to_agent", {"customer_id": "{{customer_id}}", "queue": "{{t_queue}}"})], "step",
                             mapping=[{"path": "data.ok", "variable": "tr_ok"}]),
    "end": {"name": "end", "node_type": "end_call", "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True, "transitions": [],
            "terminal": {"type": "function", "function": {"name": "call_closed", "handler": "__function__:end_call",
                         "parameters": {"type": "object", "properties": {"message_mode": {"type": "string", "default": "custom"},
                                                                         "spoken_message": {"type": "string", "default": "{{bye}}"}}}}}},
}
# promise amount must go as a number
nodes["create_promise"]["pre_actions"][0]["pre_process_code"] = (
    "try:\n    b = config.get('body')\n    if isinstance(b, dict):\n        b['amount'] = float(vars.get('p_amount'))\n        b['date'] = str(vars.get('p_date'))[:10]\nexcept Exception:\n    pass\n")
for n in ("create_promise", "schedule_callback", "transfer_to_agent", "get_account", "verify_identity"):
    nodes[n]["response_mapping"].append({"path": "data.error", "variable": n[:2] + "_err"}) if n != "verify_identity" else None
# clear stale mapped flags before each call
for n, keys in (("create_promise", ["pr_ok"]), ("schedule_callback", ["cb_ok"]), ("transfer_to_agent", ["tr_ok"]), ("get_account", ["a_ok"])):
    nodes[n]["pre_actions"][0]["pre_process_code"] = nodes[n]["pre_actions"][0].get("pre_process_code", "") or ""
    nodes[n]["pre_actions"][0]["pre_process_code"] = "".join("vars[%r] = 'none'\n" % k for k in keys) + nodes[n]["pre_actions"][0]["pre_process_code"]

close_tool = api_fn("close_call", "close_call", {"customer_id": "{{customer_id}}", "outcome": "{{outcome}}", "reason": "{{reason}}"})
close_tool["config"] = {"timeoutMs": 12000, "maxRetries": 2, "alwaysRunsAt": ["end_of_call"]}
close_tool["function"]["parameters"]["properties"]["body"]["required"] = ["customer_id", "outcome"]
close_tool["pre_process_code"] = snippets.close_pre_process(tuple(SPEC["service_failure_pair"]), "outcome", "reason", "customer_id")

wf = {
    "initial_node": "init",
    "system_prompt": "You are the digital assistant of Freya Bank on a phone call. Speak English. Say exactly the text you are given, nothing more.",
    "nodes": nodes, "global_nodes": {}, "tools": [close_tool],
    "test_variables": {"customer_id": "c_test", "first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"},
}
out = ROOT / ("out/%s.workflow.json" % SLOT)
json.dump(wf, open(out, "w"), indent=1)
print("wrote", out)
