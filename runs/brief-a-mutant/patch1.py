import os
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gen.py')
s = open(p).read()
a = s.index('nodes["human_count"]'); b = s.index('nodes["max_turns_close"]')
s = s[:a] + s[b:]
a = s.index('global_nodes = {'); b = s.index('SYSTEM = (')
new = '''def gcode(name, code):
    return [{"type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec",
             "parameters": {"type": "object", "properties": {"code": {"type": "string", "default": code}, "timeout_ms": {"type": "number", "default": 10000}}}}}]


global_nodes = {
    "g_human": {"name": "g_human", "description": "Customer asks for a human", "node_type": "code",
                "condition": {"operator": "matches_intent", "description": "The customer asks to speak to a human, a real person, an agent or an operator"},
                "excluded_nodes": ENDS + ["ask_callback", "ask_callback_again", "opening"],
                "passthrough": True, "passthrough_default_transition": "__previous__", "on_enter": {"type": "silent"},
                "pre_actions": gcode("g_human", counter_code("human_asks", spec["human_asks"]["value"], "human_state")),
                "transitions": [tr("xfer_human", "insists", anyof(eq("human_state", "final"))), tr("__previous__", "always", {"operator": "always"})]},
    "g_not_talk": {"name": "g_not_talk", "description": "Customer does not want to talk", "node_type": "code",
                   "condition": {"operator": "matches_intent", "description": "The customer says they do not want to talk / are not interested in talking / asks to stop the call"},
                   "excluded_nodes": ENDS + ["ask_callback", "ask_callback_again", "opening", "hardship_offer"],
                   "passthrough": True, "passthrough_default_transition": "__previous__", "on_enter": {"type": "silent"},
                   "pre_actions": gcode("g_not_talk", counter_code("not_talk", spec["not_talk_to_close"]["value"], "not_talk_state", ["stance", "id_stance"])),
                   "transitions": [tr("close_not_verified_declined", "second, unverified", anyof(allof(eq("not_talk_state", "final"), eq("verified_state", "no")))),
                                   tr("close_no_promise_refused", "second, verified", anyof(eq("not_talk_state", "final"))),
                                   tr("__previous__", "always", {"operator": "always"})]},
}

'''
s = s[:a] + new + s[b:]
s = s.replace('"Never say something was recorded, saved or booked unless the tool returned success. Do not end the call yourself.")',
              '"Never say something was recorded, saved or booked unless the tool returned success. Do not end the call yourself. "\n          "If the customer asks for a human, the first time ask once whether you can help them first. If the customer says they do not want to talk, the first time explain briefly why the questions or the call matter and continue.")')
open(p, 'w').write(s)
