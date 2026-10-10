"""Generate out/brief-a.workflow.json and out/brief-b.workflow.json.

    python3 dev/gen_phone_agents.py

Brief B is Brief A plus the multi-product changes of briefs/brief-b.md.
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = json.load(open(ROOT / "tools" / "openapi.json"))
BASE = API["servers"][0]["url"]

# ---------------------------------------------------------------- helpers

def body_leaf(name, spec, model_filled=True):
    leaf = {"type": spec.get("type", "string")}
    if "enum" in spec: leaf["enum"] = spec["enum"]
    leaf["default"] = "{{customer_id}}" if name == "customer_id" else "{{" + name + "}}"
    return leaf


def api_tool(name, description, descs=None, mapping=None, post=None, retries=0):
    path = API["paths"]["/" + name]["post"]
    schema = path["requestBody"]["content"]["application/json"]["schema"]
    props = {}
    for f, spec in schema["properties"].items():
        leaf = body_leaf(f, spec)
        d = (descs or {}).get(f) or spec.get("description")
        if d and f != "customer_id": leaf["description"] = d
        props[f] = leaf
    t = {
        "type": "function",
        "config": {"timeoutMs": 12000, "maxRetries": retries},
        "function": {
            "name": name,
            "handler": "__function__:api_call",
            "description": description,
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string", "default": BASE + "/" + name},
                "method": {"type": "string", "default": "POST"},
                "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                "body": {"type": "object", "properties": props, "required": [f for f in schema.get("required", []) if f != "customer_id"]},
            }},
        },
    }
    if mapping: t["response_mapping"] = [{"path": p, "variable": v} for p, v in mapping]
    if post: t["post_process_code"] = post
    return t


def code_node(name, code, target):
    assert "{{" not in code and "}}" not in code, name
    return {
        "name": name, "node_type": "code", "passthrough": True, "passthrough_default_transition": target,
        "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
        "pre_actions": [{"type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec",
                         "parameters": {"type": "object", "properties": {"code": {"type": "string", "default": code}, "timeout_ms": {"type": "number", "default": 10000}}}}}],
        "transitions": [{"target_node": target, "description": "always", "condition": {"operator": "always"}}],
    }


def anyof(*conds):
    return {"logic": "or", "conditions": list(conds)}


def eq(v, o): return {"variable": v, "operator": "equals", "operand": o}
def gt(v, o): return {"variable": v, "operator": "greater_than", "operand": o}
def isset(v): return {"variable": v, "operator": "is_set"}


def truthy(v): return [eq(v, "true"), eq(v, "True")]


def tc(target, when):
    """A transition the dialogue model fires by calling transition_to_<target>."""
    return {"target_node": target, "description": when, "is_tool_call": True, "condition": {"operator": "matches_intent", "description": when}}


def conv(name, task, tools=(), transitions=(), on_enter=None, extraction=None, max_turns=30, max_target=None):
    n = {"name": name, "node_type": "conversation", "task_message": task, "tools": list(tools), "transitions": list(transitions),
         "max_node_turns": max_turns, "on_enter_first_entry_only": True}
    if on_enter: n["on_enter"] = on_enter
    if extraction: n["extraction_schema"] = extraction
    if max_target: n["max_turn_transition"] = max_target
    return n

# ---------------------------------------------------------------- post hooks (no double braces allowed)

POST_VERIFY = """try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if isinstance(d, dict):
            allv = str(d.get('all_verified')).lower() == 'true'
            ver = str(d.get('verified')).lower() == 'true'
            ok = str(d.get('ok')).lower() == 'true'
            left = d.get('wrong_answers_left')
            if allv:
                msg = 'Both security answers are verified.'
            elif d.get('hint') == 'day_month_swapped':
                msg = 'Day and month look swapped. This does NOT count as a wrong answer. Ask the customer to say the month of their birth as a word, then call verify_identity again with the corrected date.'
            elif not ok and not ver and left is None:
                msg = 'The answer could not be checked and is NOT counted as wrong. If it was a date of birth, send it as YYYY-MM-DD (numbers only spoken as day, month, year). Otherwise ask the customer to repeat the answer.'
            elif ver:
                msg = 'Correct. Now ask the second security question: the last four digits of the phone number on file. Do not ask the date of birth again.'
            else:
                try:
                    n = int(float(left))
                except Exception:
                    n = 1
                if n > 0:
                    msg = 'That answer did not match. ' + str(n) + ' wrong answer(s) left in total. Tell the customer it did not match and ask the SAME question again. Do not ask the other question.'
                else:
                    msg = 'No wrong answers left. The security check has failed.'
            d['what_to_do_next'] = msg
except Exception:
    pass
"""

POST_PROMISE = """try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        ok = isinstance(d, dict) and str(d.get('ok')).lower() == 'true'
        if ok:
            msg = 'The promise IS recorded.'
        else:
            msg = 'FAILED: NOTHING WAS RECORDED. Do not say it is recorded or saved. If this is the first failure for this product: tell the customer there was a technical problem and that you will try once more, then call create_promise again with the same values. If it already failed once before for this product: tell the customer you could not record it.'
        if isinstance(d, dict):
            d['what_to_do_next'] = msg
        else:
            result['data'] = dict(ok=False, error=str(d), what_to_do_next=msg)
except Exception:
    pass
"""

POST_SIMPLE = """try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        ok = isinstance(d, dict) and str(d.get('ok')).lower() == 'true'
        msg = 'Done.' if ok else 'FAILED: nothing was done. Tell the customer there was a technical problem.'
        if isinstance(d, dict):
            d['what_to_do_next'] = msg
except Exception:
    pass
"""

PRE_CLOSE = """try:
    b = config.get('body')
    if isinstance(b, dict) and (b.get('outcome') in ('promise', 'paid') or not b.get('reason') or '{' in str(b.get('reason'))):
        b.pop('reason', None)
except Exception:
    pass
"""

# ---------------------------------------------------------------- code: dates (brief A section 7, rule 6)

PREPARE = """import datetime
NL = chr(10)
HOL = set(['2026-10-26', '2026-11-11', '2026-11-26', '2026-12-25', '2027-01-01'])
def isbd(d):
    return d.weekday() < 5 and d.isoformat() not in HOL
def addbd(d, n):
    x = d
    c = 0
    while c < n:
        x = x + datetime.timedelta(days=1)
        if isbd(x):
            c += 1
    return x
def nextbd(d):
    x = d
    while not isbd(x):
        x = x + datetime.timedelta(days=1)
    return x
def nm(d):
    return d.strftime('%A') + ' ' + str(d.day) + ' ' + d.strftime('%B %Y') + ' (' + d.isoformat() + ')'
def lastbd_week(monday):
    r = None
    for i in range(5):
        x = monday + datetime.timedelta(days=i)
        if isbd(x):
            r = x
    return r
try:
    now = str(vars.get('now') or '')
    today = datetime.date.fromisoformat(now[:10])
    hhmm = now[11:16] if len(now) >= 16 else '00:00'
    monday = today - datetime.timedelta(days=today.weekday())
    a1 = lastbd_week(monday)
    if a1 is None or a1 <= today:
        a1 = lastbd_week(monday + datetime.timedelta(days=7))
    early = addbd(today, 12)
    late = addbd(today, 7)
    nbd = addbd(today, 1)
    vars['dl_early'] = early.isoformat()
    vars['dl_late'] = late.isoformat()
    vars['attempt1_date'] = a1.isoformat()
    L = []
    L.append('Now is ' + now + '. Today is ' + nm(today) + '. Today ' + ('IS' if isbd(today) else 'is NOT') + ' a business day.')
    L.append('Business days are Monday to Friday except bank holidays 2026-10-26, 2026-11-11, 2026-11-26, 2026-12-25, 2027-01-01.')
    L.append('Calendar (use it, never your own calendar):')
    labels = ['this week', 'next week', 'the week after next', 'in three weeks', 'in four weeks', 'in five weeks']
    for w in range(6):
        parts = []
        for i in range(7):
            x = monday + datetime.timedelta(days=7 * w + i)
            t = x.strftime('%a') + ' ' + x.isoformat()
            if x < today:
                t += ' past'
            elif x == today:
                t += ' TODAY'
            if x.isoformat() in HOL:
                t += ' HOLIDAY'
            elif x.weekday() >= 5:
                t += ' weekend'
            parts.append(t)
        L.append('- ' + labels[w] + ': ' + ', '.join(parts))
    wd = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    th = []
    nx = []
    for i in range(7):
        th.append(wd[i] + ' ' + (monday + datetime.timedelta(days=i)).isoformat())
        nx.append(wd[i] + ' ' + (monday + datetime.timedelta(days=7 + i)).isoformat())
    L.append('"This <weekday>" = the weekday in the current week: ' + ', '.join(th) + '.')
    L.append('"Next <weekday>" = the weekday in the following calendar week: ' + ', '.join(nx) + '.')
    L.append('Tomorrow = ' + nm(today + datetime.timedelta(days=1)) + '.')
    vars['date_facts'] = NL.join(L)
    if hhmm < '10:00':
        tw = 'today (' + nm(today) + ') from 10:00 to 19:00'
    else:
        tw = 'today (' + nm(today) + ') at a time later than ' + hhmm + ' and not after 19:00'
    if hhmm >= '19:00':
        tw = 'not today (it is already past 19:00)'
    vars['callback_facts'] = ('Allowed callback slots: ' + tw + '; or the next business day, ' + nm(nbd) + ', from 10:00 to 19:00. '
        + '10:00 and 19:00 are both allowed. Any other day (including later days) or time is outside the window. '
        + 'Send the date as YYYY-MM-DD and the time as HH:MM in 24-hour form (for example eleven in the morning = 11:00, half past three in the afternoon = 15:30).')
    vars['prepare_state'] = 'ok'
except Exception as e:
    vars['date_facts'] = 'Date facts unavailable. Now is ' + str(vars.get('now')) + '.'
    vars['callback_facts'] = 'A callback is allowed today later than now, or the next business day, between 10:00 and 19:00.'
    vars['prepare_state'] = 'failed'
"""

# ---------------------------------------------------------------- code: account facts (sections 6, 7, 8, 9; brief B 1-6)

ACCOUNT = """import datetime, json, re
NL = chr(10)
HOL = set(['2026-10-26', '2026-11-11', '2026-11-26', '2026-12-25', '2027-01-01'])
MULTI = __MULTI__
def isbd(d):
    return d.weekday() < 5 and d.isoformat() not in HOL
def nm(d):
    return d.strftime('%A') + ' ' + str(d.day) + ' ' + d.strftime('%B') + ' (' + d.isoformat() + ')'
def money(x):
    return '{:,.2f}'.format(float(x))
def products():
    p = vars.get('products')
    if isinstance(p, str):
        for s in (p, p.replace(chr(39), chr(34)).replace('True', 'true').replace('False', 'false').replace('None', 'null')):
            try:
                p = json.loads(s)
                break
            except Exception:
                pass
    if isinstance(p, list) and p and isinstance(p[0], dict):
        return p
    rows = dict()
    for k in list(vars.keys()):
        m = re.search(r'products\\.(\\d+)\\.([A-Za-z_0-9]+)$', str(k))
        if m:
            rows.setdefault(int(m.group(1)), dict())[m.group(2)] = vars.get(k)
    return [rows[i] for i in sorted(rows)]
try:
    now = str(vars.get('now') or '')
    today = datetime.date.fromisoformat(now[:10])
    a1 = datetime.date.fromisoformat(str(vars.get('attempt1_date')))
    ps = products()
    if not ps:
        raise ValueError('no products')
    facts = []
    says = []
    for i, p in enumerate(ps):
        typ = str(p.get('type'))
        pid = str(p.get('product_id'))
        if typ == 'credit_card':
            label = 'credit card ending ' + str(p.get('card_last4'))
            floor = float(p.get('minimum_payment'))
            fname = 'minimum payment'
        else:
            label = 'personal loan' if typ == 'personal_loan' else ('car loan' if typ == 'car_loan' else typ.replace('_', ' '))
            floor = float(p.get('instalment_amount'))
            fname = 'instalment amount'
        due = float(p.get('past_due'))
        days = int(float(p.get('days_late')))
        if days <= 7:
            band = 'early'
            dl = datetime.date.fromisoformat(str(vars.get('dl_early')))
            att = 1
        else:
            band = 'late'
            dl = datetime.date.fromisoformat(str(vars.get('dl_late')))
            att = 2
        a1p = a1 if a1 <= dl else dl
        valid = []
        x = today
        while x <= dl:
            if isbd(x):
                valid.append(x.strftime('%a') + ' ' + x.isoformat())
            x = x + datetime.timedelta(days=1)
        hdr = ('PRODUCT ' + str(i + 1) + ': ' if MULTI else 'PRODUCT: ')
        f = [hdr + label + ', product_id ' + pid + '.',
             '  Full past-due amount: ' + money(due) + '. Days late: ' + str(days) + ' (' + band + ' band).',
             '  Floor (' + fname + '): ' + money(floor) + '. Accept any amount from ' + money(floor) + ' to ' + money(due) + ', both included.',
             '  DEADLINE (latest promise date): ' + nm(dl) + '. Any date after it cannot be recorded.',
             '  Valid promise dates (business days from today to the deadline): ' + ', '.join(valid) + '.',
             '  Persuasion attempts allowed for this product: ' + str(att) + '.',
             '  Attempt 1 offer: ' + money(due) + ' (or the floor ' + money(floor) + ' if the customer already said the full amount is too much) on ' + nm(a1p) + '.']
        if att == 2:
            f.append('  Attempt 2 offer: the floor ' + money(floor) + ' on the deadline, ' + nm(dl) + '.')
        else:
            f.append('  There is NO attempt 2 for this product (early band). After attempt 1 is refused, stop.')
        facts.append(NL.join(f))
        if MULTI:
            says.append('Your ' + label + ' has a past-due amount of ' + money(due) + ' and is ' + str(days) + ' days late.')
        else:
            says.append('your ' + label + '. The past-due amount is ' + money(due) + ' and the payment is ' + str(days) + ' days late.')
    vars['debt_facts'] = (NL + NL).join(facts)
    vars['product_count'] = str(len(ps))
    if MULTI and len(ps) > 1:
        vars['debt_statement'] = 'I am calling from the collections team about late payments. ' + ' '.join(says) + ' Can you pay all of them today?'
    elif MULTI:
        vars['debt_statement'] = 'I am calling from the collections team about a late payment. ' + says[0] + ' Can you make this payment today?'
    else:
        vars['debt_statement'] = 'I am calling from the collections team about a late payment on ' + says[0] + ' Can you make this payment today?'
    vars['account_state'] = 'ok'
except Exception as e:
    vars['debt_facts'] = 'Account facts could not be computed. Use the get_account result above. Error: ' + str(e)
    vars['debt_statement'] = 'I am calling from the collections team about a late payment on your account.'
    vars['account_state'] = 'failed'
"""

# ---------------------------------------------------------------- code: closings

def close_code(outcome, reason, farewell, kind):
    """kind: plain | transfer | promise_guard (promise wins) | needs_promise"""
    lines = ["try:",
             "    title = str(vars.get('title') or '')",
             "    last = str(vars.get('last_name') or '')",
             "    who = (title + ' ' + last).strip()",
             "    rec = False",
             "    for k in ('promise_id', 'create_promise_response.data.promise_id'):",
             "        v = vars.get(k)",
             "        if v and str(v) not in ('None', 'null', ''):",
             "            rec = True",
             "    try:",
             "        if int(float(vars.get('create_promise_success_count') or 0)) > 0 and str(vars.get('create_promise_response.data.ok')).lower() == 'true':",
             "            rec = True",
             "    except Exception:",
             "        pass",
             f"    outcome = {outcome!r}",
             f"    reason = {reason!r}",
             f"    fare = {farewell!r}"]
    if kind == "transfer":
        lines += ["    q = str(vars.get('transfer_to_agent_args.queue') or '')",
                  "    reason = dict(restructuring='restructuring', general='human', support='support').get(q, 'human')"]
    if kind == "promise_guard":
        lines += ["    if rec:",
                  "        outcome = 'promise'",
                  "        reason = ''",
                  "        fare = 'You will receive a text message confirming this promise. Thank you for your time, ' + who + '. Goodbye.'"]
    if kind == "needs_promise":
        lines += ["    if not rec:",
                  "        outcome = 'no_promise'",
                  "        reason = 'refused'",
                  "        fare = 'Thank you for your time, ' + who + '. Goodbye.'"]
    lines += ["    vars['outcome'] = outcome",
              "    vars['reason'] = reason",
              "    vars['farewell'] = fare.replace('WHO', who)",
              "except Exception:",
              f"    vars['outcome'] = {outcome!r}",
              f"    vars['reason'] = {reason!r}",
              "    vars['farewell'] = 'Thank you for your time. Goodbye.'"]
    return "\n".join(lines) + "\n"


BYE = "Thank you for your time, WHO. Goodbye."
CLOSES = {
    # node: (outcome, reason, farewell, kind)
    "close_callback": ("not_reached", "callback", "Thank you, we will call back then. Goodbye.", "plain"),
    "close_no_callback": ("not_reached", "no_callback", "Thank you for your time. Goodbye.", "plain"),
    "close_wrong_number": ("not_reached", "wrong_number", "Thank you for letting me know, and sorry for the trouble. Goodbye.", "plain"),
    "close_deceased": ("not_reached", "deceased", "I am sorry for your loss. Thank you, goodbye.", "plain"),
    "close_unclear": ("not_reached", "unclear", "Thank you for your time. Goodbye.", "plain"),
    "close_failed": ("not_verified", "failed", "I am sorry, I could not verify your identity, so I cannot continue. Please use the Freya Bank mobile app or visit a branch. Thank you for your time, goodbye.", "plain"),
    "close_declined": ("not_verified", "declined", "I understand. Thank you for your time. Goodbye.", "plain"),
    "close_transfer": ("transferred", "human", "I am transferring you now. Thank you for your time, WHO. Goodbye.", "transfer"),
    "close_paid": ("paid", "", "Thank you. Payments can take one business day to appear on your account. Thank you for your time, WHO. Goodbye.", "promise_guard"),
    "close_dispute": ("no_promise", "dispute", BYE, "promise_guard"),
    "close_hardship": ("no_promise", "hardship", BYE, "promise_guard"),
    "close_refused": ("no_promise", "refused", BYE, "promise_guard"),
    "close_service_error": ("no_promise", "service_error", "I am sorry, I could not record your promise because of a technical problem. Thank you for your time, WHO. Goodbye.", "promise_guard"),
    "close_promise": ("promise", "", "Your promise is recorded. You will receive a text message confirming this promise. Thank you for your time, WHO. Goodbye.", "needs_promise"),
}

# ---------------------------------------------------------------- prompts

SYSTEM = """You are the digital assistant of Freya Bank, on an outbound phone call. Speak English. Keep every turn to one or two short sentences. Address the customer as {{title}} {{last_name}}.

Rules that hold in every step:
- If asked whether you are a robot or an AI: say you are Freya Bank's digital assistant, then continue where you were.
- If asked whether this is a scam: say they can verify the call by phoning Freya Bank's customer service number, then continue where you were.
- If asked something you cannot answer from the facts you were given: say you do not have that information. Never invent figures, dates or reasons.
- Never offer a discount, a waiver, an instalment plan or any term that is not in your instructions.
- When an instruction says to call a tool, call it. Saying that you did it is not enough. Call at most one tool per message.
- After every tool result, read its what_to_do_next field if present and obey it, then speak to the customer or call the next tool. Never end a turn with nothing.
- Never say a promise, a callback or a transfer is done unless the tool result says it succeeded.
- To end the call, call the matching tool whose name starts with transition_to_close. The thanks and goodbye are then said for you, so do not say goodbye yourself."""

OPENING_TASK = """You opened the call and asked whether you are speaking with {{title}} {{last_name}}. You must find out who is on the line.

Do not say why you are calling. Never say "collections", "debt", "payment", "loan", "card", an amount or any product. This applies to everyone, including relatives.

- Only "yes", "that's me", "speaking" or the customer's own name counts as confirmation. "Hello", "go ahead" and "who is this" do not.
- If it is not yet confirmed, ask once more: "Am I speaking with {{title}} {{last_name}}?". If the person asked a question, answer it first (who you are: Freya Bank's digital assistant; robot; scam), then ask. That ask is the second ask.
- If after your second ask it is still not confirmed, call transition_to_close_unclear.
- If the person says twice that they do not want to talk, call transition_to_close_declined.
- If the person asks for a human: ask once whether you can help first. If they insist, call transfer_to_agent with queue general.
No other tool is allowed in this step."""

THIRD_TASK = """The person on the line is NOT {{title}} {{last_name}}. Do not say why you are calling. Say nothing about any account, debt, payment, product or amount, even if they ask or offer to pay. They may not answer security questions. If they ask what it is about, say you can only discuss it with {{title}} {{last_name}}.

Your job: ask when {{title}} {{last_name}} can be reached.
{{callback_facts}}

- If they give a day and time inside the allowed slots, call schedule_callback with that date and time right away.
- If they give only a day or only a vague time (for example "in the morning"), ask for the exact time.
- If the day or time is outside the allowed slots, say so and ask once for another time. If the second answer is also outside, call transition_to_close_no_callback.
- If they say they do not know or will not give a time, ask once for a time; if still none, call transition_to_close_no_callback.
- If they say the number does not belong to {{first_name}} {{last_name}} or they do not know this person, call transition_to_close_wrong_number.
- If they say {{title}} {{last_name}} has died, call transition_to_close_deceased right away and ask nothing else.

Dates for reference:
{{date_facts}}"""

SECURITY_TASK = """The person confirmed they are {{title}} {{last_name}}. Verify identity with two security questions, one at a time: first the date of birth, then the last four digits of the phone number on file. Until both pass, do not say why you are calling and never mention collections, debt, payment, a product or an amount.

- CALL verify_identity every time the customer gives an answer. field date_of_birth with the answer as YYYY-MM-DD, whatever way the customer said it (a date said only as numbers is day, then month, then year: "03 04 1990" is 1990-04-03). field phone_last4 with exactly four digits.
- Obey the what_to_do_next field of each result: ask the second question, ask the same question again, or ask for the month as a word.
- Never ask a question that already passed.
- If the customer refuses to answer, or asks what the call is about instead of answering: explain once that the questions protect their account and ask again. If they refuse again or ask again what it is about, call transition_to_close_declined.
- If the customer asks for a human: ask once whether you can help first. If they insist, call transfer_to_agent with queue general.
Only verify_identity, transfer_to_agent and the transition tools are allowed in this step."""

DEBT_TASK_A = """The customer is verified. You already said (fixed line): {{debt_statement}}

ACCOUNT FACTS (computed by code; trust them, never compute your own):
{{debt_facts}}

DATES:
{{date_facts}}

CHECK THESE FIRST, every turn, before anything else:
1. Hardship: the customer mentions illness, a death in the family or job loss. Say ONE short sentence of sympathy, make NO persuasion attempt, and offer to connect them with the customer support team. If they accept, call transfer_to_agent with queue support. If they decline, call transition_to_close_hardship. If they still name a date or an amount themselves, handle it as a promise below.
2. "I already paid" (a payment of this past-due amount): call transition_to_close_paid. Take no promise.
3. Dispute: "this debt is not mine", "I never had this product", or a claim that the product was closed or paid off in the past. Do not argue. Call transition_to_close_dispute.
4. A request for a new payment plan, lower instalments or restructuring: do not describe any plan. Call transfer_to_agent with queue restructuring.
5. A request for a human: ask once whether you can help first. If they insist, call transfer_to_agent with queue general.
6. The customer says for the second time that they do not want to talk: call transition_to_close_refused.

GETTING THE PROMISE:
- You propose every amount. NEVER ask "how much can you pay?". The first ask is the full past-due amount today (already asked).
- A date or an amount the customer proposes is never a refusal. Check it:
  - Amount from the floor up to the full amount, both included: accept it. Below the floor: say it cannot be recorded and offer the floor once; if they do not accept the floor, that is a flat refusal.
  - "The full amount is too much": offer the floor once and say the rest stays overdue. If they refuse the floor, that is a flat refusal.
  - Date: it must be a VALID PROMISE DATE from the facts. A weekend day or holiday not after the deadline: offer the next business day. A date after the deadline: say the latest date you can record is the deadline (say it) and offer it; if they refuse it, that is a flat refusal.
  - A vague period ("next week", "end of the month", "when my salary comes", "the week after next"): ask ONCE for the exact day. If they still give none, propose the deadline.
- A flat refusal or a non-answer (including "no" to paying today with no date and no amount) uses one persuasion attempt. Make the next attempt from the facts: attempt 1, then attempt 2 only if the facts allow it. Never repeat an offer already refused. When the allowed attempts are used up and the customer refuses again, call transition_to_close_refused.
- When the customer agrees to an amount and a date: read back the product, the amount and the date and ask "Do you confirm?". If they change the date or the amount, check it again and read it back again.
- Only after a clear yes, CALL create_promise with product_id, amount (a number) and date (YYYY-MM-DD).
- If create_promise fails: do not say recorded. Say there was a technical problem and you will try once more, and call create_promise again with the same values. If it fails again, call transition_to_close_service_error.
- One promise only. Never offer anything else."""

DEBT_TASK_B = """The customer is verified. You already said (fixed line): {{debt_statement}}

ACCOUNT FACTS, one block per late product, in order (computed by code; trust them, never compute your own). Each product has its OWN band, deadline, floor and number of persuasion attempts:
{{debt_facts}}

DATES:
{{date_facts}}

CHECK THESE FIRST, every turn:
1. Hardship: the customer mentions illness, a death in the family or job loss. Say ONE short sentence of sympathy, make NO persuasion attempt on any product, and offer to connect them with the customer support team. If they accept, call transfer_to_agent with queue support (add no notes). If they decline, treat every product still without an agreement as hardship (no persuasion), then finish (see FINISHING). If they still name a date or an amount themselves, handle it as a promise.
2. "I already paid" for a product: say payments can take one business day to appear. That product gets no promise; it will be noted paid. Continue with the other products.
3. Dispute on a product ("not mine", "I never had it", "it was closed or paid off in the past"): do not argue, no promise for it; it will be noted dispute. Continue with the other products.
4. A request for a new payment plan, lower instalments or restructuring: do not describe any plan. Call transfer_to_agent with queue restructuring right away. Do not record promises that are agreed but not yet recorded. Add no notes.
5. A request for a human: ask once whether you can help first. If they insist, call transfer_to_agent with queue general. Add no notes.
6. The customer says for the second time that they do not want to talk: treat every product without a recorded promise as refused and go to FINISHING.

ORDER OF THE CALL:
A. You already asked whether they can pay all of them today. If yes (full amounts, today), go to READ-BACK.
B. If not, go through the products ONE BY ONE in the order of the facts. Do not ask about today again. For each product, start at its attempt 1 offer, and say which product you are talking about.
C. If the customer names one date for everything: use it for every product where it is valid. For a product whose deadline is before that date, use that product's own deadline instead and say so.

RULES FOR EACH PRODUCT:
- You propose every amount. NEVER ask "how much can you pay?".
- A date or an amount the customer proposes is never a refusal. Check it against THAT product's facts:
  - Amount from the floor up to the full amount, both included: accept. Below the floor: say it cannot be recorded and offer the floor once; if not accepted, that is a flat refusal.
  - "The full amount is too much": offer the floor once and say the rest stays overdue. If they refuse the floor, that is a flat refusal.
  - Date: must be one of that product's VALID PROMISE DATES. Weekend or holiday not after the deadline: offer the next business day. After the deadline: say the latest date you can record for that product is its deadline and offer it; refusing it is a flat refusal.
  - Vague period: ask ONCE for the exact day; if still none, propose the deadline.
- A flat refusal or non-answer uses one persuasion attempt OF THAT PRODUCT. Make that product's next attempt from its facts (attempt 2 only if its facts allow it). Never repeat a refused offer. When its attempts are used up, that product is refused; move to the next product.

READ-BACK: when every product is settled, read ALL agreed promises back together in one message (product, amount, date for each) and ask ONE "Do you confirm?". If they change something, check it and read back again.

RECORDING: after the clear yes, CALL create_promise once per agreed product (product_id, amount as a number, date YYYY-MM-DD), one call per message, in order. If one fails, say there was a technical problem and try it once more. If it fails again, that product gets a service_error note; keep the promises that were recorded. Never say a promise is recorded unless its result says so.

FINISHING (not after a transfer):
1. For EACH product without a recorded promise, CALL add_note with its product_id and reason: refused, hardship, dispute, paid or service_error. One call per message. This applies even when no product got a promise.
2. Then end the call with exactly one transition tool:
   - at least one promise recorded: transition_to_close_promise
   - no promise and every product noted paid: transition_to_close_paid
   - otherwise use the reason of the FIRST product in the facts order whose note is not paid: transition_to_close_refused, transition_to_close_hardship, transition_to_close_dispute or transition_to_close_service_error."""

# ---------------------------------------------------------------- tools

TOOL_VERIFY = api_tool("verify_identity", "Check ONE security answer. CALL it every time the customer gives a date of birth or phone digits.",
                       descs={"field": "date_of_birth or phone_last4.", "answer": "date_of_birth as YYYY-MM-DD (numbers only spoken are day, month, year). phone_last4 as exactly four digits."},
                       post=POST_VERIFY)
TOOL_TRANSFER = api_tool("transfer_to_agent", "Hand the call to a person. CALL it when the rules say to transfer. queue: restructuring (new plan / lower instalments), support (hardship, customer accepted support), general (customer insists on a human).",
                         descs={"queue": "One of: restructuring, support, general."}, post=POST_SIMPLE)
TOOL_CALLBACK = api_tool("schedule_callback", "Book a callback. CALL it as soon as the person gives a day and time inside the allowed callback slots.",
                         descs={"date": "Callback date, YYYY-MM-DD.", "time": "Callback time, HH:MM, 24-hour."}, post=POST_SIMPLE)
TOOL_PROMISE = api_tool("create_promise", "Record one payment promise for one product. CALL it only after the customer said a clear yes to the read-back.",
                        descs={"product_id": "product_id from the account facts, copied exactly.", "amount": "The agreed amount as a number, for example 637.5.", "date": "The agreed date, YYYY-MM-DD."},
                        mapping=[("data.promise_id", "promise_id")], post=POST_PROMISE)
TOOL_NOTE = api_tool("add_note", "Record why a product ended without a promise. CALL it once for each product without a recorded promise, at the end, before closing. Never after or before a transfer.",
                     descs={"product_id": "product_id from the account facts, copied exactly.", "reason": "One of: refused, hardship, dispute, paid, service_error.", "text": "One short sentence."},
                     post=POST_SIMPLE)

close_body_tool = api_tool("close_call", "Record how the call ended. outcome promise, paid, transferred (reason restructuring, human, support), no_promise (reason refused, hardship, dispute, service_error), not_verified (reason failed, declined), not_reached (reason callback, no_callback, wrong_number, deceased, unclear).",
                           descs={"outcome": "How the call ended.", "reason": "Reason for the outcome. Leave empty for promise and paid."})
close_body_tool["config"]["alwaysRunsAt"] = ["end_of_call"]
close_body_tool.pop("post_process_code", None)
close_body_tool["pre_process_code"] = PRE_CLOSE
close_body_tool["function"]["parameters"]["properties"]["body"]["properties"]["outcome"]["default"] = "{{outcome}}"
close_body_tool["function"]["parameters"]["properties"]["body"]["properties"]["reason"]["default"] = "{{reason}}"

TRANSFER_DONE = {"target_node": "close_transfer", "description": "The transfer tool succeeded",
                 "condition": anyof(gt("transfer_to_agent_success_count", 0))}

# ---------------------------------------------------------------- workflow


def build(multi):
    nodes = {}
    nodes["prepare"] = code_node("prepare", PREPARE, "opening")
    nodes["opening"] = conv(
        "opening", OPENING_TASK, tools=[TOOL_TRANSFER],
        on_enter={"type": "tts", "text": "Hello, I am a digital assistant calling from Freya Bank, and this call is recorded. Am I speaking with {{title}} {{last_name}}?"},
        extraction=[{"name": "line_status", "type": "string", "enum_values": ["confirmed", "other_person", "wrong_number", "deceased", "none"], "min_confidence": 0.6,
                     "description": "Who is on the line, from the person's LAST message. confirmed: they clearly say yes, that's me, speaking, or say the asked-for name is their own. other_person: they say they are someone else (a relative, partner, colleague) or that the asked-for person is not there or not available. wrong_number: they say the number does not belong to the asked-for person or they do not know that person. deceased: they say the asked-for person has died. none: anything else, for example hello, go ahead, who is this, a question, or unclear."}],
        transitions=[
            TRANSFER_DONE,
            {"target_node": "security", "description": "Customer confirmed", "condition": anyof(eq("line_status", "confirmed"))},
            {"target_node": "close_deceased", "description": "Customer died", "condition": anyof(eq("line_status", "deceased"))},
            {"target_node": "close_wrong_number", "description": "Wrong number", "condition": anyof(eq("line_status", "wrong_number"))},
            {"target_node": "third_party", "description": "Someone else answered", "condition": anyof(eq("line_status", "other_person"))},
            tc("close_unclear", "After the second ask the person has still not confirmed who they are."),
            tc("close_declined", "The person said twice that they do not want to talk."),
        ], max_turns=6, max_target="close_unclear")
    nodes["third_party"] = conv(
        "third_party", THIRD_TASK, tools=[TOOL_CALLBACK],
        on_enter={"type": "llm"},
        transitions=[
            {"target_node": "close_callback", "description": "Callback booked", "condition": anyof(gt("schedule_callback_success_count", 0))},
            tc("close_no_callback", "No callback time inside the allowed slots after asking twice, or the person will not give one."),
            tc("close_wrong_number", "The number does not belong to the customer."),
            tc("close_deceased", "The person says the customer has died."),
        ], max_turns=10, max_target="close_no_callback")
    nodes["security"] = conv(
        "security", SECURITY_TASK, tools=[TOOL_VERIFY, TOOL_TRANSFER],
        on_enter={"type": "tts", "text": "Thank you, {{title}} {{last_name}}. To protect your account I need to ask two security questions. First, what is your date of birth?"},
        transitions=[
            TRANSFER_DONE,
            {"target_node": "load_account", "description": "Both answers verified",
             "condition": anyof(*truthy("verify_identity_response.data.all_verified"))},
            {"target_node": "close_failed", "description": "Three wrong answers",
             "condition": anyof(eq("verify_identity_response.data.wrong_answers_left", "0"), eq("verify_identity_response.data.wrong_answers_left", "0.0"))},
            tc("close_declined", "The customer refused the security questions a second time, or asked a second time what the call is about instead of answering."),
        ], max_turns=16, max_target="close_declined")
    nodes["load_account"] = {
        "name": "load_account", "node_type": "api_request", "passthrough": True, "passthrough_default_transition": "account_facts",
        "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
        "pre_actions": [{k: v for k, v in api_tool("get_account", "Get the late products.", retries=2).items() if k != "post_process_code"}],
        "response_mapping": [{"path": "data.products", "variable": "products"}, {"path": "data.ok", "variable": "account_ok"}],
        "transitions": [{"target_node": "account_facts", "description": "always", "condition": {"operator": "always"}}],
    }
    nodes["account_facts"] = code_node("account_facts", ACCOUNT.replace("__MULTI__", "True" if multi else "False"), "debt")
    debt_tr = [TRANSFER_DONE]
    if not multi:
        debt_tr += [
            {"target_node": "close_promise", "description": "The promise was recorded",
             "condition": anyof(isset("promise_id"), *truthy("create_promise_response.data.ok"))},
            {"target_node": "close_service_error_auto", "description": "create_promise failed twice",
             "condition": anyof(gt("create_promise_failure_count", 1))},
        ]
    else:
        debt_tr += [tc("close_promise", "At least one promise was recorded and every product without a promise has its note.")]
    debt_tr += [
        tc("close_paid", "The customer already paid." if not multi else "No promise recorded and every product was noted paid."),
        tc("close_dispute", "The customer disputes the debt." if not multi else "No promise recorded; the first product whose note is not paid was noted dispute."),
        tc("close_hardship", "Hardship and the customer declined the support team." if not multi else "No promise recorded; the first product whose note is not paid was noted hardship."),
        tc("close_refused", "All persuasion attempts used and refused, or the customer said twice they do not want to talk." if not multi else "No promise recorded; the first product whose note is not paid was noted refused."),
        tc("close_service_error", "create_promise failed twice." if not multi else "No promise recorded; the first product whose note is not paid was noted service_error."),
    ]
    tools = [TOOL_PROMISE, TOOL_TRANSFER] + ([TOOL_NOTE] if multi else [])
    nodes["debt"] = conv("debt", DEBT_TASK_B if multi else DEBT_TASK_A, tools=tools,
                         on_enter={"type": "tts", "text": "{{debt_statement}}"},
                         transitions=debt_tr, max_turns=60, max_target="close_refused")
    for name, (o, r, fare, kind) in CLOSES.items():
        nodes[name] = code_node(name, close_code(o, r, fare, kind), "hangup")
    if not multi:
        o, r, fare, kind = CLOSES["close_service_error"]
        nodes["close_service_error_auto"] = code_node("close_service_error_auto", close_code(o, r, fare, kind), "hangup")
    nodes["hangup"] = {
        "name": "hangup", "node_type": "end_call", "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True, "transitions": [],
        "terminal": {"type": "function", "function": {"name": "call_closed", "handler": "__function__:end_call",
                     "parameters": {"type": "object", "properties": {"message_mode": {"type": "string", "default": "custom"},
                                                                       "spoken_message": {"type": "string", "default": "{{farewell}}"}}}}},
    }
    return {
        "initial_node": "prepare",
        "system_prompt": SYSTEM,
        "nodes": nodes,
        "global_nodes": {},
        "tools": [close_body_tool],
        "test_variables": {"customer_id": "c_test", "first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"},
    }


def check(wf):
    s = json.dumps(wf)
    assert ": null" not in s, "null in workflow"
    for k, n in wf["nodes"].items():
        for t in n.get("transitions", []):
            assert t["target_node"] in wf["nodes"], (k, t["target_node"])
        if n.get("max_turn_transition"): assert n["max_turn_transition"] in wf["nodes"]


if __name__ == "__main__":
    (ROOT / "out").mkdir(exist_ok=True)
    for slot, multi in (("brief-a", False), ("brief-b", True)):
        wf = build(multi); check(wf)
        json.dump(wf, open(ROOT / "out" / f"{slot}.workflow.json", "w"), indent=1)
        print("wrote", slot, len(wf["nodes"]), "nodes")
