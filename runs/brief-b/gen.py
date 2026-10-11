import json, sys, textwrap
sys.path.insert(0, "lib")
import snippets
from snippets import code

SLOT = "brief-b"
spec = json.load(open("out/spec.json"))
api = json.load(open("inputs/openapi.json"))
BASE = api["servers"][0]["url"].rstrip("/")
SPECSUB = {k: spec[k] for k in ("holidays", "bands", "floor_fields", "cb_start", "cb_end", "max_products", "next_week_mode", "say", "outcomes", "queues")}

body = open("out/step_body.py").read()
lg = textwrap.indent(snippets.loop_guard("service_error", 40), "    ")
body = body.replace("    LOOPGUARD\n", lg)
STEP = code(body, SPECSUB)
STEP = STEP.replace("}}", "} }").replace("{{", "{ {")


def codenode(name, src, nxt_transitions, default):
    return {"name": name, "node_type": "code", "passthrough": True, "passthrough_default_transition": default,
            "on_enter": {"type": "silent"},
            "pre_actions": [{"type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec",
                             "parameters": {"type": "object", "properties": {"code": {"type": "string", "default": src}, "timeout_ms": {"type": "number", "default": 10000}}}}}],
            "transitions": nxt_transitions + [{"target_node": default, "description": "always", "condition": {"operator": "always"}}]}


def apinode(name, path, fields, retries=0):
    props = api["paths"]["/" + path]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]
    b = {}
    for f, var in fields.items():
        assert f in props, f
        e = {"type": props[f].get("type", "string"), "default": "{{" + var + "}}"}
        if "enum" in props[f]: e["enum"] = props[f]["enum"]
        b[f] = e
    return {"name": name, "node_type": "api_request", "passthrough": True, "passthrough_default_transition": "step",
            "on_enter": {"type": "silent"},
            "pre_actions": [{"type": "function", "config": {"timeoutMs": 12000, "maxRetries": retries}, "function": {
                "name": path, "handler": "__function__:api_call", "description": path,
                "parameters": {"type": "object", "properties": {
                    "url": {"type": "string", "default": BASE + "/" + path}, "method": {"type": "string", "default": "POST"},
                    "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                    "body": {"type": "object", "properties": b, "required": list(fields)}}}}}],
            "response_mapping": [], "transitions": [{"target_node": "step", "description": "always", "condition": {"operator": "always"}}]}


def eq(var, val):
    return {"logic": "or", "conditions": [{"variable": var, "operator": "equals", "operand": val}]}


INTENTS = {
    "none": "nothing new was said",
    "yes": "the customer says yes, confirms, agrees, 'that's me', 'speaking', or says their own name",
    "no": "a plain no (for example to paying today, to an offer, or to the read-back), with no date and no amount",
    "not_me": "the speaker says they are not the customer (a relative, partner, someone else), even if they also ask a question",
    "wrong_number": "the number does not belong to the customer / nobody of that name here",
    "deceased": "the customer has died",
    "purpose": "asks what the call is about / why we are calling",
    "human": "asks to speak to a person, a human, an agent",
    "not_talk": "says they do not want to talk / not interested / will not answer questions / hang up",
    "paid": "says they already paid this past-due amount (a past payment)",
    "dispute": "says the debt or product is not theirs, never had it, or the product was closed or paid off in the past",
    "hardship": "mentions illness, a death in the family or job loss",
    "plan": "explicitly asks for a new payment plan, instalments, lower instalments or a longer term; naming a date they can pay on is NOT a plan",
    "too_much": "says the amount is too much / cannot afford the full amount, without naming an amount",
    "change_recorded": "asks to change or cancel a promise already recorded",
    "discount": "asks for a discount, a waiver, a reduction of the debt or other special terms (an explicit request for a payment plan or instalments is plan, not discount)",
    "unclear": "the answer is cut off, unclear or only small talk (hello, go ahead)",
    "other": "anything else",
}

talk = {"name": "talk", "node_type": "conversation", "on_enter": {"type": "tts", "text": "{{say}}"},
        "task_message": "You are Freya Bank's digital assistant on a phone call. Speak English.\nSay exactly this text: \"{{say}}\"\nSay exactly this text. Never promise a transfer, a callback or any other action that the text does not state. Do not add facts, amounts or dates.",
        "role_message": "", "tools": [], "interruptible": True, "max_node_turns": 3, "max_turn_transition": "step",
        "extraction_schema": [
            {"name": "intent", "type": "string", "enum_values": list(INTENTS), "min_confidence": 0.5,
             "description": "The main thing the customer said in their LAST message. " + " | ".join(k + ": " + v for k, v in INTENTS.items()) + ". If they give a date or an amount they can pay, use yes/no/other only as fits and fill date_words/amount_words."},
            {"name": "side_q", "type": "string", "enum_values": ["none", "robot", "scam", "other_question"], "min_confidence": 0.5,
             "description": "A side question in the last message: robot = asks if this is a robot or AI; scam = asks if this is a scam or real; other_question = another question about the account; none = no question."},
            {"name": "date_words", "type": "string", "min_confidence": 0.5,
             "description": "The customer's own words for a day or date in the last message, copied as said (e.g. 'next Friday', 'the 20th', 'tomorrow', 'end of the month'). 'none' if no day was said."},
            {"name": "time_words", "type": "string", "min_confidence": 0.5,
             "description": "The customer's own words for a clock time in the last message, as said (e.g. 'three pm', '11:30', 'eleven in the morning'), with the day if said. 'none' if none."},
            {"name": "amount_words", "type": "string", "min_confidence": 0.5,
             "description": "An amount of money the customer says they can pay, as said (e.g. '200', 'one hundred fifty'). 'none' if none. Not a date, not phone digits."},
            {"name": "answer_words", "type": "string", "min_confidence": 0.5,
             "description": "The customer's answer to a security question, copied as said: a date of birth (or part of it) or phone digits. 'none' if none."},
        ],
        "transitions": [{"target_node": "step", "description": "after every customer reply", "condition": {"operator": "always"}}],
        "truncation_strategy": "keep_all", "passthrough": False}

acts = ["talk", "verify", "account", "promise", "note", "callback", "transfer", "end"]
step_tr = [{"target_node": a if a not in ("end",) else "end", "description": "act " + a, "condition": eq("act", a)} for a in acts]

START = ("try:\n    vars['say'] = " + repr(spec["opening"]) + ".replace('{title}', str(vars.get('title') or '')).replace('{last_name}', str(vars.get('last_name') or ''))\nexcept Exception:\n    vars['say'] = 'Hello.'\n"
         "vars['st'] = 'confirm'\nvars['asks'] = 1\nvars['act'] = 'talk'\nvars['intent'] = 'none'\nvars['side_q'] = 'none'\nvars['outcome'] = ''\nvars['reason'] = ''\nvars['bye'] = " + repr(spec["say"]["goodbye"]) + "\n")

nodes = {
    "start": codenode("start", START, [], "talk"),
    "talk": talk,
    "step": codenode("step", STEP, step_tr, "talk"),
    "verify": apinode("verify", "verify_identity", {"customer_id": "customer_id", "field": "v_field", "answer": "v_answer"}),
    "account": apinode("account", "get_account", {"customer_id": "customer_id"}),
    "promise": apinode("promise", "create_promise", {"customer_id": "customer_id", "product_id": "c_pid", "amount": "c_amt", "date": "c_date"}),
    "note": apinode("note", "add_note", {"customer_id": "customer_id", "product_id": "n_pid", "reason": "n_reason", "text": "n_text"}),
    "callback": apinode("callback", "schedule_callback", {"customer_id": "customer_id", "date": "cb_date", "time": "cb_time"}),
    "transfer": apinode("transfer", "transfer_to_agent", {"customer_id": "customer_id", "queue": "queue"}),
    "end": {"name": "end", "node_type": "end_call", "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True, "transitions": [],
            "terminal": {"type": "function", "function": {"name": "call_closed", "handler": "__function__:end_call",
                         "parameters": {"type": "object", "properties": {"message_mode": {"type": "string", "default": "custom"},
                                                                          "spoken_message": {"type": "string", "default": "{{bye}}"}}}}}},
}
# map product fields flat as a fallback reader
fields = ["product_id", "type", "card_last4", "past_due", "days_late", "minimum_payment", "instalment_amount"]
nodes["account"]["response_mapping"] = [{"path": "data.products.%d.%s" % (i, f), "variable": "p%d_%s" % (i, f)} for i in range(6) for f in fields]

cprops = api["paths"]["/close_call"]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]
close_tool = {"type": "function", "config": {"timeoutMs": 12000, "maxRetries": 2, "alwaysRunsAt": ["end_of_call"]},
              "function": {"name": "close_call", "handler": "__function__:api_call", "description": "Record how the call ended.",
                           "parameters": {"type": "object", "properties": {
                               "url": {"type": "string", "default": BASE + "/close_call"}, "method": {"type": "string", "default": "POST"},
                               "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                               "body": {"type": "object", "required": ["customer_id", "outcome"], "properties": {
                                   "customer_id": {"type": "string", "default": "{{customer_id}}"},
                                   "outcome": {"type": "string", "enum": cprops["outcome"]["enum"], "default": "{{outcome}}"},
                                   "reason": {"type": "string", "default": "{{reason}}"}}}}}},
              "pre_process_code": snippets.close_pre_process(("not_reached", "unclear"), "outcome", "reason", "customer_id")}

wf = {"nodes": nodes, "tools": [close_tool], "global_nodes": {}, "initial_node": "start", "system_prompt": "",
      "test_variables": {"customer_id": "c_test", "first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"}}
json.dump(wf, open("out/%s.workflow.json" % SLOT, "w"), indent=1)
print("ok", len(STEP))
