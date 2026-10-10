import json, pathlib

BASE = "https://freya-bank-mock.freyavoice.workers.dev/v1/"
OUT = pathlib.Path(__file__).resolve().parent.parent / "out" / "brief-a.workflow.json"

HDR = {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}}


def tool(name, path, fields, required, desc, post=None, pre=None, baked=None):
    props = {"customer_id": {"type": "string", "default": "{{customer_id}}"}}
    for k, spec in fields.items():
        s = dict(spec)
        s["default"] = (baked or {}).get(k, "{{%s}}" % k)
        props[k] = s
    t = {
        "type": "function",
        "config": {"timeoutMs": 12000, "maxRetries": 0},
        "function": {
            "name": name,
            "handler": "__function__:api_call",
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "default": BASE + path},
                    "method": {"type": "string", "default": "POST"},
                    "headers": HDR,
                    "body": {"type": "object", "properties": props, "required": required},
                },
            },
        },
    }
    if pre:
        t["pre_process_code"] = pre
    if post:
        t["post_process_code"] = post
    return t


def hook(ok_text, bad_text, extra=""):
    return (
        "try:\n"
        "    if isinstance(result, dict):\n"
        "        result.pop('header', None)\n"
        "        d = result.get('data')\n"
        "        good = isinstance(d, dict) and d.get('ok') in (True, 'true', 'True')\n"
        "        txt = %r if good else %r\n"
        "        if isinstance(d, dict):\n"
        "            d['what_to_do_next'] = txt\n"
        "        else:\n"
        "            result['what_to_do_next'] = txt\n"
        "%s"
        "except Exception:\n"
        "    pass\n"
    ) % (ok_text, bad_text, extra)


VERIFY_POST = (
    "try:\n"
    "    if isinstance(result, dict):\n"
    "        result.pop('header', None)\n"
    "        d = result.get('data')\n"
    "        if isinstance(d, dict):\n"
    "            if d.get('hint') == 'day_month_swapped':\n"
    "                t = 'Day and month look swapped. This does NOT count as a wrong answer. Ask the customer to say the date of birth again with the month as a word, then send it again.'\n"
    "            elif d.get('all_verified') in (True, 'true', 'True'):\n"
    "                t = 'Both answers passed. Say nothing about the account. The call moves on by itself.'\n"
    "            elif d.get('ok') in (True, 'true', 'True') and d.get('verified') in (True, 'true', 'True'):\n"
    "                t = 'This answer passed. Ask the next security question now (phone last four digits if you have not asked it yet).'\n"
    "            elif d.get('ok') in (True, 'true', 'True'):\n"
    "                t = 'This answer was wrong. Tell the customer it did not match and ask the same question again. Do not reveal the right answer.'\n"
    "            else:\n"
    "                t = 'The value could not be read and it was not counted as wrong. Ask the customer to repeat it and send it again as YYYY-MM-DD.'\n"
    "            d['what_to_do_next'] = t\n"
    "        else:\n"
    "            result['what_to_do_next'] = 'The check service failed. Nothing was counted. Ask the same question again and call verify_identity again.'\n"
    "except Exception:\n"
    "    pass\n"
)

PROMISE_POST = hook(
    "The promise IS recorded. Tell the customer it is recorded, in one short sentence. If another late product of this customer still has no promise and no outcome, go on with that product. Otherwise call transition_to_close_promise now and do not say goodbye.",
    "The promise was NOT recorded. Do not say it is recorded. If this is the first failure for this promise, call create_promise once more with the same values. If it already failed twice, call transition_to_close_service_error.",
    "        if good:\n            vars['promise_recorded'] = 'yes'\n",
)
TRANSFER_POST = hook(
    "The transfer was started. Say nothing more. The call closes by itself.",
    "The transfer failed. Tell the customer you could not transfer them right now. Then continue with the call.",
)
CALLBACK_POST = hook(
    "The callback is booked. Say nothing more. The call closes by itself.",
    "The callback was NOT booked. Do not say it is booked. Ask the person for another time inside the allowed window, once.",
)

CLOSE_PRE = (
    "try:\n"
    "    b = config.get('body')\n"
    "    if isinstance(b, dict) and (b.get('outcome') in ('promise', 'paid') or not b.get('reason')):\n"
    "        b.pop('reason', None)\n"
    "except Exception:\n"
    "    pass\n"
)

# ---------------------------------------------------------------- tools
verify_identity = tool(
    "verify_identity", "verify_identity",
    {
        "field": {"type": "string", "enum": ["date_of_birth", "phone_last4"], "description": "Which answer this is: date_of_birth or phone_last4."},
        "answer": {"type": "string", "description": "date_of_birth as YYYY-MM-DD (read numeric dates as day, month, year). phone_last4 as four digits."},
    },
    ["field", "answer"],
    "Check one security answer. CALL it every time the customer gives the date of birth or the last four phone digits. Saying it passed is not enough: call the tool.",
    post=VERIFY_POST,
)
create_promise = tool(
    "create_promise", "create_promise",
    {
        "product_id": {"type": "string", "description": "product_id of the product, copied unchanged from the get_account result."},
        "amount": {"type": "number", "description": "Amount the customer confirmed."},
        "date": {"type": "string", "description": "Promise date as YYYY-MM-DD, confirmed by the customer."},
    },
    ["product_id", "amount", "date"],
    "Record one payment promise. CALL it only after the customer said a clear yes to the read-back of product, amount and date. One promise per product.",
    post=PROMISE_POST,
)
schedule_callback = tool(
    "schedule_callback", "schedule_callback",
    {
        "date": {"type": "string", "description": "Callback date as YYYY-MM-DD."},
        "time": {"type": "string", "description": "Callback time as HH:MM, 24 hour, from 10:00 to 19:00."},
    },
    ["date", "time"],
    "Book a callback. CALL it when the person names a date and time inside the allowed callback window.",
    post=CALLBACK_POST,
)


def transfer(name, queue, when):
    return tool(name, "transfer_to_agent", {"queue": {"type": "string", "enum": [queue], "description": "Queue: " + queue}}, ["queue"],
                "Hand the call to a person (queue %s). CALL it %s." % (queue, when),
                post=TRANSFER_POST, baked={"queue": queue})


transfer_support = transfer("transfer_support", "support", "when the customer accepted being connected to customer support after hardship")
transfer_restructuring = transfer("transfer_restructuring", "restructuring", "when the customer asks for a new payment plan or lower instalments")
transfer_human = transfer("transfer_human", "general", "when the customer insists on speaking to a human, after you already asked once whether you can help")

close_call = {
    "type": "function",
    "config": {"timeoutMs": 12000, "maxRetries": 0, "alwaysRunsAt": ["end_of_call"]},
    "function": {
        "name": "close_call",
        "handler": "__function__:api_call",
        "description": "Record how the call ended.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "default": BASE + "close_call"},
                "method": {"type": "string", "default": "POST"},
                "headers": HDR,
                "body": {
                    "type": "object",
                    "required": ["outcome"],
                    "properties": {
                        "customer_id": {"type": "string", "default": "{{customer_id}}"},
                        "outcome": {"type": "string", "enum": ["promise", "paid", "transferred", "no_promise", "not_verified", "not_reached"], "default": "{{outcome}}", "description": "How the call ended."},
                        "reason": {"type": "string", "default": "{{reason}}", "description": "Reason for the outcome. Leave out for promise and paid."},
                    },
                },
            },
        },
    },
    "pre_process_code": CLOSE_PRE,
}

# ---------------------------------------------------------------- code
PREPARE = r"""
import datetime
NL = chr(10)
try:
    now = str(vars.get('now') or '')
    today = datetime.date.fromisoformat(now[:10])
    hhmm = now[11:16] if len(now) >= 16 else '00:00'
    hol = set(['2026-10-26', '2026-11-11', '2026-11-26', '2026-12-25', '2027-01-01'])
    def isbd(d):
        return d.weekday() < 5 and d.isoformat() not in hol
    def addbd(d, n):
        c = 0
        x = d
        while c < n:
            x = x + datetime.timedelta(days=1)
            if isbd(x):
                c += 1
        return x
    def nm(d):
        return d.strftime('%a') + ' ' + d.isoformat()
    def lastbd(monday):
        r = None
        for i in range(5):
            x = monday + datetime.timedelta(days=i)
            if isbd(x):
                r = x
        return r
    monday = today - datetime.timedelta(days=today.weekday())
    lb = lastbd(monday)
    if lb is None or lb <= today:
        lb = lastbd(monday + datetime.timedelta(days=7))
    de = addbd(today, 12)
    dl = addbd(today, 7)
    nbd = addbd(today, 1)
    lines = []
    lines.append('DATE FACTS (computed by code, trust them over your own calendar):')
    lines.append('Now: ' + now + '. Today is ' + nm(today) + '. Today is a business day: ' + ('yes' if isbd(today) else 'NO (weekend or holiday), so today is not a valid promise date.'))
    lines.append('Deadline for days_late 1 to 7 (early band, 1 persuasion attempt): ' + nm(de))
    lines.append('Deadline for days_late 8 to 45 (late band, 2 persuasion attempts): ' + nm(dl))
    lines.append('Persuasion attempt 1 date (last business day of this week, or of next week if today is that day): ' + nm(lb))
    lines.append('Next business day after today: ' + nm(nbd))
    lines.append('Bank holidays: 2026-10-26, 2026-11-11, 2026-11-26, 2026-12-25, 2027-01-01.')
    labels = ['THIS WEEK', 'NEXT WEEK', 'THE WEEK AFTER NEXT', 'THREE WEEKS FROM NOW']
    for w in range(4):
        parts = []
        for i in range(7):
            x = monday + datetime.timedelta(days=7 * w + i)
            tag = nm(x)
            if x < today:
                tag += ' [past]'
            elif x == today:
                tag += ' [today]'
            if not isbd(x):
                tag += ' [not a business day]'
            parts.append(tag)
        lines.append(labels[w] + ': ' + '; '.join(parts))
    for w in range(4):
        for i in range(7):
            x = monday + datetime.timedelta(days=7 * w + i)
            if x >= today and not isbd(x):
                lines.append('If the customer names ' + nm(x) + ' (not a business day), offer ' + nm(addbd(x, 1)) + ' (if that is not after the deadline).')
    lines.append('"Next <weekday>" means that weekday in NEXT WEEK. "This <weekday>" means that weekday in THIS WEEK.')
    lines.append('')
    lines.append('CALLBACK WINDOW: only today (' + today.isoformat() + ') at a time later than ' + hhmm + ' and from 10:00 to 19:00, or the next business day (' + nbd.isoformat() + ') from 10:00 to 19:00. 10:00 and 19:00 are both allowed. Any other day or time is outside the window.')
    vars['date_facts'] = NL.join(lines)
    vars['deadline_early'] = de.isoformat()
    vars['deadline_late'] = dl.isoformat()
    vars['prepare_state'] = 'ok'
except Exception:
    vars['date_facts'] = 'DATE FACTS: not available. Work out dates from the call variable now with care.'
    vars['prepare_state'] = 'failed'
"""

CLOSES = {
    "callback": ("not_reached", "callback", "Thank you. We will call you back at the time we agreed. Goodbye."),
    "no_callback": ("not_reached", "no_callback", "I am sorry, I cannot book a callback at that time. Thank you, goodbye."),
    "wrong_number": ("not_reached", "wrong_number", "I am sorry for the inconvenience. Goodbye."),
    "deceased": ("not_reached", "deceased", "I am sorry for your loss. Goodbye."),
    "unclear": ("not_reached", "unclear", "I am sorry, I could not confirm who I am speaking with. Goodbye."),
    "failed": ("not_verified", "failed", "I could not verify your identity. Please use the Freya Bank mobile app or visit a branch. Thank you, goodbye."),
    "declined": ("not_verified", "declined", "I understand. Thank you for your time. Goodbye."),
    "support": ("transferred", "support", "I am connecting you with our customer support team now. Thank you, goodbye."),
    "restructuring": ("transferred", "restructuring", "I am transferring you to a colleague who can help with that. Thank you, goodbye."),
    "human": ("transferred", "human", "I am transferring you to a colleague now. Thank you, goodbye."),
    "paid": ("paid", "", "Payments can take one business day to appear, so I will not take a promise now. Thank you, goodbye."),
    "dispute": ("no_promise", "dispute", "I understand. Thank you for your time. Goodbye."),
    "hardship": ("no_promise", "hardship", "I understand, I will not take a promise now. Thank you, goodbye."),
    "refused": ("no_promise", "refused", "Understood. Thank you for your time. Goodbye."),
    "service_error": ("no_promise", "service_error", "I am sorry, something went wrong on our side and I could not complete this. Thank you, goodbye."),
    "promise": ("promise", "", "Thank you for your time. Goodbye."),
}


def close_code(out, reason, fare):
    return (
        "try:\n"
        "    rec = False\n"
        "    for k in ('create_promise_response.data.ok', 'promise_recorded'):\n"
        "        if str(vars.get(k)) in ('true', 'True', 'yes'):\n"
        "            rec = True\n"
        "    outcome = %r\n"
        "    reason = %r\n"
        "    fare = %r\n"
        "    if rec and outcome == 'no_promise':\n"
        "        outcome = 'promise'\n"
        "        reason = ''\n"
        "    if outcome == 'promise' and not rec:\n"
        "        outcome = 'no_promise'\n"
        "        reason = 'refused'\n"
        "    if rec and outcome in ('promise', 'transferred'):\n"
        "        fare = 'You will receive a text message confirming this promise. ' + fare\n"
        "    vars['outcome'] = outcome\n"
        "    vars['reason'] = reason\n"
        "    vars['farewell'] = fare\n"
        "except Exception:\n"
        "    vars['outcome'] = %r\n"
        "    vars['reason'] = %r\n"
        "    vars['farewell'] = %r\n"
    ) % (out, reason, fare, out, reason, fare)


def code_node(name, code, nxt):
    return {
        "name": name,
        "node_type": "code",
        "passthrough": True,
        "passthrough_default_transition": nxt,
        "on_enter": {"type": "silent"},
        "disable_inactivity_monitor": True,
        "pre_actions": [{
            "type": "function",
            "function": {
                "name": "code_exec",
                "handler": "__function__:code_exec",
                "parameters": {"type": "object", "properties": {
                    "code": {"type": "string", "default": code},
                    "timeout_ms": {"type": "number", "default": 10000}}},
            },
        }],
        "transitions": [{"target_node": nxt, "description": "always", "condition": {"operator": "always"}}],
    }


def eq(var, *vals):
    return {"logic": "or", "conditions": [{"variable": var, "operator": "equals", "operand": v} for v in vals]}


def ok_cond(var):
    return eq(var, "true", "True")


def tr(target, desc, cond=None, tool=False):
    t = {"target_node": target, "description": desc}
    if tool:
        t["is_tool_call"] = True
        t["condition"] = {"operator": "matches_intent", "description": desc}
    else:
        t["condition"] = cond
    return t


def close_tool(key, desc):
    return tr("close_" + key, desc, tool=True)


nodes = {}
nodes["prepare"] = code_node("prepare", PREPARE, "confirm_name")

# ---------------------------------------------------------------- confirm_name
nodes["confirm_name"] = {
    "name": "confirm_name",
    "node_type": "conversation",
    "on_enter": {"type": "tts", "text": "Hello, I am a digital assistant calling from Freya Bank, and this call is recorded. Am I speaking with {{title}} {{last_name}}?"},
    "on_enter_first_entry_only": True,
    "task_message": (
        "Goal: find out who is on the line. The opening line already said you are a digital assistant from Freya Bank, that the call is recorded, and asked 'Am I speaking with {{title}} {{last_name}}?'. That was the FIRST ask.\n"
        "Never say 'collections', 'debt', 'payment', 'late', or the name of any product, and never say why you are calling.\n"
        "Only 'yes', 'that's me', 'speaking' or the customer's own name counts as confirmation. 'Hello', 'go ahead', 'who is this', 'what is this about' do not.\n"
        "If the reply is not a confirmation and not a different person: answer a question the person asked in one short sentence (who you are: Freya Bank's digital assistant; are you a robot or AI: you are Freya Bank's digital assistant; is this a scam: they can verify the call by phoning Freya Bank's customer service number; what it is about: you can explain after a short identity check), then ask 'Am I speaking with {{title}} {{last_name}}?' again. That is the SECOND and last ask.\n"
        "If the reply to the second ask is still not a clear confirmation, call transition_to_close_unclear.\n"
        "If the person asks for a human: ask once whether you can help first. If they insist, call transfer_human.\n"
        "If the person says twice that they do not want to talk, call transition_to_close_declined.\n"
        "Do not ask the security questions yet. Do not call any tool except transfer_human."
    ),
    "tools": [transfer_human],
    "max_node_turns": 10,
    "max_turn_transition": "close_unclear",
    "transitions": [
        tr("close_human", "The human transfer started", ok_cond("transfer_human_response.data.ok")),
        tr("security", "The person clearly confirms they are the customer: says yes, that's me, speaking, or says the customer's own name",
           {"operator": "matches_intent", "description": "The person clearly confirms they are the customer: says yes, that's me, speaking, or says the customer's own name"}),
        tr("third_party", "A different person answers: says they are not the customer, a relative or colleague, that the customer is not available, that this is a wrong number, or that the customer has died",
           {"operator": "matches_intent", "description": "A different person answers: says they are not the customer, a relative or colleague, that the customer is not available, that this is a wrong number, or that the customer has died"}),
        close_tool("unclear", "The reply to the second ask is still not a clear confirmation"),
        close_tool("declined", "The person said twice that they do not want to talk"),
    ],
}

# ---------------------------------------------------------------- third_party
nodes["third_party"] = {
    "name": "third_party",
    "node_type": "conversation",
    "task_message": (
        "You are NOT talking to the customer. Never say why you are calling and never mention the account, debt, payment or any product, even if the person offers to pay or asks. Do not ask security questions.\n"
        "React to the person's last message:\n"
        "- The number does not belong to the customer: call transition_to_close_wrong_number, say nothing else.\n"
        "- The customer has died: call transition_to_close_deceased, say nothing else (the closing line says sorry).\n"
        "- Otherwise ask when {{title}} {{last_name}} can be reached.\n"
        "{{date_facts}}\n"
        "When the person gives a day and time inside the callback window, call schedule_callback with the date as YYYY-MM-DD and the time as HH:MM. A day or time outside the window must never be booked: ask ONCE for another time. If that is also outside the window, or the person gives none, call transition_to_close_no_callback.\n"
        "Say a callback is booked only after schedule_callback returned ok true."
    ),
    "tools": [schedule_callback],
    "max_node_turns": 10,
    "max_turn_transition": "close_no_callback",
    "transitions": [
        tr("close_callback", "The callback was booked", ok_cond("schedule_callback_response.data.ok")),
        close_tool("wrong_number", "The person says the number does not belong to the customer"),
        close_tool("deceased", "The person says the customer has died"),
        close_tool("no_callback", "No valid callback time was agreed after asking twice, or the person gives no time"),
    ],
}

# ---------------------------------------------------------------- security
nodes["security"] = {
    "name": "security",
    "node_type": "conversation",
    "task_message": (
        "The customer confirmed who they are. Do the identity check now. You do not tell why the bank is calling: if asked, say you can explain after the security check.\n"
        "Ask ONE question at a time: first the date of birth, then the last four digits of the phone number on file. Call verify_identity after each answer (field date_of_birth, then phone_last4).\n"
        "Send the date of birth as YYYY-MM-DD whatever way it was said. A date given only as numbers is day, then month, then year.\n"
        "Follow the what_to_do_next line of each tool result. A wrong answer may be asked again; the service counts them and the call moves on by itself after three wrong answers. Never reveal a correct answer. Never say anything about the account.\n"
        "If the customer does not want to answer, or asks what the call is about instead of answering: explain ONCE that the questions protect their account and ask again. If they refuse again or ask again what the call is about, call transition_to_close_declined.\n"
        "If the customer says twice that they do not want to talk, call transition_to_close_declined.\n"
        "If the customer asks for a human: ask once whether you can help first. If they insist, call transfer_human."
    ),
    "tools": [verify_identity, transfer_human],
    "max_node_turns": 25,
    "max_turn_transition": "close_declined",
    "transitions": [
        tr("close_human", "The human transfer started", ok_cond("transfer_human_response.data.ok")),
        tr("load_account", "Both security answers passed", eq("verify_identity_response.data.all_verified", "true", "True")),
        tr("close_failed", "Three wrong answers in total", eq("verify_identity_response.data.wrong_answers_left", "0")),
        close_tool("declined", "The customer refused to answer the security questions a second time, or asked a second time what the call is about, or said twice they do not want to talk"),
    ],
}

# ---------------------------------------------------------------- load_account
nodes["load_account"] = {
    "name": "load_account",
    "node_type": "api_request",
    "passthrough": True,
    "passthrough_default_transition": "close_service_error",
    "on_enter": {"type": "silent"},
    "disable_inactivity_monitor": True,
    "pre_actions": [{
        "type": "function",
        "config": {"timeoutMs": 12000, "maxRetries": 2},
        "function": {
            "name": "get_account",
            "handler": "__function__:api_call",
            "description": "Get the late products.",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string", "default": BASE + "get_account"},
                "method": {"type": "string", "default": "POST"},
                "headers": HDR,
                "body": {"type": "object", "properties": {"customer_id": {"type": "string", "default": "{{customer_id}}"}}, "required": []},
            }},
        },
    }],
    "response_mapping": [{"path": "data.ok", "variable": "account_ok"}],
    "transitions": [
        tr("debt", "The account was loaded", {"logic": "or", "conditions": [
            {"variable": "account_ok", "operator": "equals", "operand": "true"},
            {"variable": "account_ok", "operator": "equals", "operand": "True"},
            {"variable": "get_account_response.data.ok", "operator": "equals", "operand": "true"},
            {"variable": "get_account_response.data.ok", "operator": "equals", "operand": "True"}]}),
        tr("close_service_error", "The account could not be loaded", {"operator": "always"}),
    ],
}

# ---------------------------------------------------------------- debt
DEBT = """The customer {{title}} {{last_name}} is verified. The get_account result is in the conversation above. It lists the late products with product_id, type, card_last4, past_due, days_late, minimum_payment (credit card) or instalment_amount (loans).

{{date_facts}}

FIRST MESSAGE IN THIS STEP: say you are calling from the collections team about a late payment. Name the product in words: 'credit card ending <card_last4>', 'personal loan' or 'car loan'. State the past-due amount and how many days late it is. Then ask 'Can you make this payment today?' (this asks for the full past-due amount). If several products are late, handle them one at a time, each with its own promise.

BAND (read days_late of the product and pick the matching deadline; never mix them up): days_late 1 to 7 = early: deadline is the early deadline above, 1 persuasion attempt. days_late 8 to 45 = late: deadline is the late deadline above, 2 persuasion attempts.
FLOOR: minimum_payment for a credit card, instalment_amount for a personal loan or car loan.

DATES. A promise date must be today or later, a business day (see the calendar above), and not after the deadline.
- A weekend day or holiday that is not after the deadline: offer the next business day: the very next calendar day that has no [not a business day] tag in the calendar (a holiday Monday is followed by Tuesday, not by the next week). Check the calendar tags, never guess.
- A date after the deadline: say the latest date you can record is the deadline and offer it. If the customer refuses the deadline, it is a flat refusal.
- A vague period ('next week', 'end of the month', 'when my salary comes'): ask ONCE for the exact day. If they still give none, propose the deadline.
- 'Next <weekday>' = that weekday in NEXT WEEK. 'This <weekday>' = that weekday in THIS WEEK. Use the calendar lines.

AMOUNTS. Ask for the full past-due amount first. Never ask 'how much can you pay?'. You propose every amount.
- If the customer says the full amount is too much, offer the floor ONCE and say the rest stays overdue. If they refuse the floor, it is a flat refusal.
- If the customer proposes an amount from the floor up to the full amount (both included), accept it. Below the floor: say it cannot be recorded and offer the floor once. If they do not accept the floor, it is a flat refusal.

GETTING THE PROMISE. A date or an amount the customer proposes is never a refusal: handle it with the date and amount rules. A flat refusal, or a non-answer, or 'no' to paying today with no date and no amount, uses ONE persuasion attempt:
- Attempt 1: propose the full past-due amount (or the floor, if the customer already said the full amount is too much) on the attempt-1 date from the facts above.
- Attempt 2 (late band only): propose the floor amount on the deadline.
When the attempts are used up and the customer refuses again, stop and call transition_to_close_refused. Never repeat an offer the customer already refused. Never offer a discount, waiver, instalment plan or any term not written here.

HARDSHIP. If the customer mentions illness, a death in the family or job loss: say one short sentence of sympathy, make NO persuasion attempt, and offer to connect them with the customer support team. If they accept, call transfer_support. If they decline, call transition_to_close_hardship. If they still name a date or an amount themselves, record the promise with the rules above. This comes before the persuasion rules.

OTHER THINGS.
- 'I already paid': say payments can take one business day to appear, take no promise, call transition_to_close_paid. (Only for a payment of this past-due amount.)
- 'This debt is not mine', 'I never had this product', or the product was closed or paid off in the past: do not argue, take no promise, call transition_to_close_dispute.
- A request for a new payment plan or lower instalments: describe no plan, call transfer_restructuring.
- A request for a human: ask once whether you can help first. If they insist, call transfer_human.
- If the customer says twice that they do not want to talk, call transition_to_close_refused.
- A recorded promise cannot be changed or cancelled in this call. If asked, say they can change it in the mobile app.

CONFIRM AND RECORD. When date and amount are agreed, read the product, the amount and the date back and ask 'Do you confirm?'. Call create_promise only after a clear yes. If the customer changes the date or amount at this step, check the new value against the rules and read it back again. Say the promise is recorded only after create_promise returned ok true. Use the exact product_id from get_account. Follow the what_to_do_next line of the tool result.
Never use the word 'recorded', 'saved' or 'booked' before create_promise has returned ok true; before that, say 'confirm' or 'note down'. After a failed create_promise do not say recorded.
Do not say goodbye yourself."""

nodes["debt"] = {
    "name": "debt",
    "node_type": "conversation",
    "task_message": DEBT,
    "tools": [create_promise, transfer_support, transfer_restructuring, transfer_human],
    "max_node_turns": 80,
    "max_turn_transition": "close_refused",
    "transitions": [
        tr("close_support", "Transfer to support started", ok_cond("transfer_support_response.data.ok")),
        tr("close_restructuring", "Transfer to restructuring started", ok_cond("transfer_restructuring_response.data.ok")),
        tr("close_human", "Transfer to a human started", ok_cond("transfer_human_response.data.ok")),
        close_tool("promise", "A promise was recorded (create_promise returned ok true) and no other late product still needs one"),
        close_tool("paid", "The customer says they already paid this past-due amount"),
        close_tool("dispute", "The customer says the debt is not theirs, or they never had the product, or it was closed or paid off in the past"),
        close_tool("hardship", "The customer mentioned illness, a death in the family or job loss and declined the support transfer"),
        close_tool("refused", "The persuasion attempts are used up and the customer refuses, or the customer said twice they do not want to talk"),
        close_tool("service_error", "create_promise failed twice"),
    ],
}

for key, (out, reason, fare) in CLOSES.items():
    nodes["close_" + key] = code_node("close_" + key, close_code(out, reason, fare), "hangup")

nodes["hangup"] = {
    "name": "hangup",
    "node_type": "end_call",
    "on_enter": {"type": "silent"},
    "disable_inactivity_monitor": True,
    "transitions": [],
    "terminal": {
        "type": "function",
        "function": {
            "name": "call_closed",
            "handler": "__function__:end_call",
            "parameters": {"type": "object", "properties": {
                "message_mode": {"type": "string", "default": "custom"},
                "spoken_message": {"type": "string", "default": "{{farewell}}"}}},
        },
    },
}

SYSTEM = (
    "You are the digital assistant of Freya Bank on an outbound phone call. Speak English. Keep every turn to one or two short sentences. Address the customer as {{title}} {{last_name}}.\n"
    "Rules that hold in every step:\n"
    "- If asked whether you are a robot or an AI: say you are Freya Bank's digital assistant and continue.\n"
    "- If asked whether this is a scam: say they can verify the call by phoning Freya Bank's customer service number, and continue.\n"
    "- If asked something you cannot answer from the tools or these instructions: say you do not have that information. Never invent figures, dates or reasons.\n"
    "- Never offer a discount, waiver, instalment plan or any term not given in your instructions.\n"
    "- Never say that something is recorded, saved or booked unless the matching tool returned ok true. If a tool fails, say so.\n"
    "- Call at most one tool per message. After every tool result, speak to the customer or call the next tool. Never send an empty turn.\n"
    "- Do not say goodbye yourself. The call closes by itself with a goodbye after you call a closing step.\n"
    "- The current date and time is {{now}}. Use no other clock."
)

wf = {
    "initial_node": "prepare",
    "system_prompt": SYSTEM,
    "nodes": nodes,
    "global_nodes": {},
    "tools": [close_call],
    "test_variables": {"customer_id": "c_test", "first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"},
}

# sanity: no template braces inside code strings
for n in nodes.values():
    for a in n.get("pre_actions", []):
        c = a["function"]["parameters"]["properties"].get("code", {}).get("default", "")
        assert "{{" not in c and "}}" not in c, n["name"]

OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(wf, indent=1))
print("wrote", OUT)
