import json, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))
import snippets
from snippets import code

SPEC = json.load(open(ROOT / "out/spec.json"))
API = json.load(open(ROOT / "inputs/openapi.json"))
BASE = SPEC["base_url"].rstrip("/")
assert BASE == API["servers"][0]["url"].rstrip("/")
SLOT = sys.argv[1] if len(sys.argv) > 1 else "brief-b"


def req_props(path):
    return API["paths"][path]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]


INTENTS = ["none", "yes", "no", "not_me", "wrong_number", "deceased", "robot", "scam", "what_about", "question", "human",
           "refuse_talk", "refuse_id", "refuse", "cant_today", "too_much", "paid", "dispute", "hardship", "plan", "discount",
           "change_promise", "other", "unclear"]
INTENT_DESC = ("What the customer's LAST message does, one value. yes: confirms (yes, that's me, speaking, own name, accepts the offer or read-back). "
 "no: a plain no (to 'am I speaking with', the offer, or paying today). not_me: someone else answered (a relative, 'she is not here', 'I am her husband'). "
 "wrong_number: the number does not belong to the customer. deceased: the customer has died. robot: asks if you are a robot or AI. "
 "scam: asks if this is a scam or fraud. what_about: asks what the call is about or who is calling. question: any other question. "
 "human: asks for a human, a person, an agent. refuse_talk: says they do not want to talk. refuse_id: will not answer the security question. "
 "refuse: refuses to pay with no date and no amount. cant_today: cannot pay today (if they also name a day, still fill when_words). "
 "too_much: the full amount is too much. paid: says they already paid this amount. dispute: says the debt or product is not theirs, never had it, or it was closed or paid off in the past, or a charge is wrong. "
 "hardship: illness, a death in the family, or job loss. plan: explicitly asks for a new payment plan, instalments, restructuring or lower instalments (naming a date they can pay is NOT a plan). "
 "discount: asks for a discount, waiver or lower amount. change_promise: wants to change or cancel an already recorded promise. "
 "other: anything else. unclear: cut off, hello, go ahead, or cannot tell. none: nothing said.")


def f(name, desc, enum=None, typ="string"):
    d = {"name": name, "type": typ, "description": desc, "min_confidence": 0.5}
    if enum: d["enum_values"] = enum
    return d


EXTRACTION = [
    f("intent", INTENT_DESC, INTENTS),
    f("dob_day", "Day of the month of the customer's date of birth, as digits (1-31), from the last message only. 'none' if not said."),
    f("dob_month", "Month of the customer's date of birth as a number 1-12 ('June' -> 6), from the last message only. When only numbers are said, read them as day, then month, then year. 'none' if not said."),
    f("dob_year", "Year of birth as four digits ('nineteen eighty seven' -> 1987, 'two thousand and five' -> 2005), last message only. 'none' if not said."),
    f("digits", "Phone digits the customer said in the last message, as digits only ('four eight two one' -> 4821). 'none' if not said."),
    f("when_words", "The customer's own words for a day they offer (to pay, or for a callback), copied as said: 'tomorrow', 'next Friday', 'the 20th', 'October 20', 'today', 'next week'. Only from the last message. A day they say they already paid on is not filled. 'none' if no day."),
    f("time_words", "The customer's own words for a time of day, copied as said ('eleven in the morning', '3 pm', '15:30'). Last message only. 'none' if no time."),
    f("amount", "An amount of money the customer offers to pay, as a number with a dot for decimals ('two hundred fifty' -> 250). Last message only. 'none' if no amount."),
    f("product_ref", "Which product the customer's last message is about: credit_card, personal_loan, car_loan, all (all/both/everything), or none.", ["none", "all", "credit_card", "personal_loan", "car_loan"]),
]


def code_node(name, body_code, transitions, default):
    return {"name": name, "node_type": "code", "passthrough": True, "passthrough_default_transition": default,
            "on_enter": {"type": "silent"},
            "pre_actions": [{"type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec",
                "description": "run node code",
                "parameters": {"type": "object", "properties": {"code": {"type": "string", "default": body_code},
                                                                 "timeout_ms": {"type": "number", "default": 10000}}}}}],
            "transitions": transitions + [{"target_node": default, "description": "always", "condition": {"operator": "always"}}]}


def api_node(name, tool, path, body, mapping, retries=0):
    props = req_props(path)
    for k in body: assert k in props, (path, k)
    bp = {}
    for k, v in body.items():
        p = {"type": props[k].get("type", "string"), "default": v}
        if "enum" in props[k]: p["enum"] = props[k]["enum"]
        bp[k] = p
    return {"name": name, "node_type": "api_request", "passthrough": True, "passthrough_default_transition": "brain",
            "on_enter": {"type": "silent"},
            "pre_actions": [{"type": "function", "config": {"timeoutMs": 12000, "maxRetries": retries},
                "function": {"name": tool, "handler": "__function__:api_call", "description": tool,
                    "parameters": {"type": "object", "properties": {
                        "url": {"type": "string", "default": BASE + path},
                        "method": {"type": "string", "default": "POST"},
                        "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                        "body": {"type": "object", "properties": bp, "required": list(body)}}}}}],
            "response_mapping": [{"path": p, "variable": v} for p, v in mapping],
            "transitions": [{"target_node": "brain", "description": "always", "condition": {"operator": "always"}}]}


S = SPEC["sentences"]
init_body = """
def _f(s):
    return s.replace('{title}', str(vars.get('title') or '')).replace('{last_name}', str(vars.get('last_name') or ''))
vars['say'] = _f(SPEC['sentences']['opening'])
vars['q'] = _f(SPEC['sentences']['confirm_q'])
vars['last_say'] = vars['say']
vars['st'] = 'confirm'
vars['act'] = 'talk'
vars['outcome'] = ''
vars['reason'] = ''
vars['pending'] = ''
vars['P_json'] = '[]'
for k in ['intent', 'dob_day', 'dob_month', 'dob_year', 'digits', 'when_words', 'time_words', 'amount', 'product_ref']:
    vars[k] = 'none'
"""
brain_code = code(open(ROOT / "out/brain_body.py").read(), SPEC)
assert "{{" not in brain_code and "}}" not in brain_code


def eq(var, val):
    return {"logic": "or", "conditions": [{"variable": var, "operator": "equals", "operand": val, "mode": "exact"}]}


ACTS = [("end", "end"), ("verify", "api_verify"), ("account", "api_account"), ("promise", "api_promise"),
        ("note", "api_note"), ("callback", "api_callback"), ("transfer", "api_transfer")]
nodes = {}
nodes["init"] = code_node("init", "import json\nSPEC = json.loads(" + repr(json.dumps({"sentences": S})) + ")\n" + init_body, [], "talk")
nodes["brain"] = code_node("brain", brain_code,
    [{"target_node": t, "description": "act " + a, "condition": eq("act", a)} for a, t in ACTS], "talk")
nodes["talk"] = {"name": "talk", "node_type": "conversation",
    "on_enter": {"type": "tts", "text": "{{say}}"},
    "task_message": "You are Freya Bank's digital assistant on a phone call, speaking English. Say exactly this text: \"{{say}}\". "
        "Never promise a transfer, a callback or any other action that the text does not state. Do not add anything else.",
    "role_message": "", "extraction_schema": EXTRACTION, "tools": [],
    "transitions": [{"target_node": "brain", "description": "after every customer message", "condition": {"operator": "always"}}],
    "max_node_turns": 2, "max_turn_transition": "brain", "interruptible": True,
    "truncation_strategy": "keep_recent", "truncation_window_size": 6}
nodes["end"] = {"name": "end", "node_type": "end_call", "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
    "transitions": [], "terminal": {"type": "function", "function": {"name": "call_closed", "handler": "__function__:end_call",
        "parameters": {"type": "object", "properties": {"message_mode": {"type": "string", "default": "custom"},
                                                         "spoken_message": {"type": "string", "default": "{{say}}"}}}}}}
std = [("data.ok", "r_ok"), ("data.error", "r_error")]
nodes["api_verify"] = api_node("api_verify", "verify_identity", "/verify_identity",
    {"customer_id": "{{customer_id}}", "field": "{{v_field}}", "answer": "{{v_answer}}"},
    std + [("data.verified", "r_verified"), ("data.all_verified", "r_all"), ("data.hint", "r_hint")])
pm = []
for i in range(6):
    for fld in ["product_id", "type", "card_last4", "past_due", "days_late", "minimum_payment", "instalment_amount"]:
        pm.append(("data.products.%d.%s" % (i, fld), "p%d_%s" % (i, fld)))
nodes["api_account"] = api_node("api_account", "get_account", "/get_account", {"customer_id": "{{customer_id}}"}, std + pm)
nodes["api_promise"] = api_node("api_promise", "create_promise", "/create_promise",
    {"customer_id": "{{customer_id}}", "product_id": "{{v_product_id}}", "amount": "{{v_amount}}", "date": "{{v_date}}"}, std)
nodes["api_note"] = api_node("api_note", "add_note", "/add_note",
    {"customer_id": "{{customer_id}}", "product_id": "{{v_product_id}}", "reason": "{{v_note}}"}, std)
nodes["api_callback"] = api_node("api_callback", "schedule_callback", "/schedule_callback",
    {"customer_id": "{{customer_id}}", "date": "{{v_cb_date}}", "time": "{{v_cb_time}}"}, std)
nodes["api_transfer"] = api_node("api_transfer", "transfer_to_agent", "/transfer_to_agent",
    {"customer_id": "{{customer_id}}", "queue": "{{v_queue}}"}, std)

cprops = req_props("/close_call")
close_tool = {"type": "function", "config": {"timeoutMs": 12000, "maxRetries": 2, "alwaysRunsAt": ["end_of_call"]},
    "function": {"name": "close_call", "handler": "__function__:api_call", "description": "Record how the call ended.",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string", "default": BASE + "/close_call"},
            "method": {"type": "string", "default": "POST"},
            "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
            "body": {"type": "object", "required": ["customer_id", "outcome"], "properties": {
                "customer_id": {"type": "string", "default": "{{customer_id}}"},
                "outcome": {"type": "string", "enum": cprops["outcome"]["enum"], "default": "{{outcome}}"},
                "reason": {"type": "string", "default": "{{reason}}"}}}}}},
    "pre_process_code": snippets.close_pre_process(tuple(SPEC["outcomes"]["service_error"]), "outcome", "reason", "customer_id")}

wf = {"nodes": nodes, "tools": [close_tool], "global_nodes": {}, "initial_node": "init", "system_prompt":
      "You are Freya Bank's digital assistant on a phone call. Speak English. Say only the text you are given.",
      "test_variables": {"customer_id": "c_test", "first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"}}
json.dump(wf, open(ROOT / ("out/%s.workflow.json" % SLOT), "w"), indent=1)
print("ok", len(brain_code))
