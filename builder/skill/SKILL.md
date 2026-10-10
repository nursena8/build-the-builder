---
name: build-phone-agent
description: Build a Freya phone agent from a bank's brief and tool API, check it offline and save it. Use when asked to build a phone agent from a brief.
---

# Build a phone agent from a brief

You work alone in the current folder, and it holds everything you need: the brief and the tool API file under `inputs/`, `docs/`, `examples/base-agent.json`, `freya.py`, the tested helpers in `lib/`, and the checkers in `tools/`.
Nobody is available to answer questions, so decide from the brief and keep going. The brief and the tool API file are your only source of facts: every number, date, name and rule in the agent comes from them.
You have a fixed time budget (in the prompt). Save a working agent early, then improve it.

## The idea

A phone call is a chain of small steps. Let **code** decide everything that can be computed (dates, bands, deadlines, counters, outcomes) and let the **model** do only what needs language: talk, listen, hand back the customer's words. Give the model one finished fact at a time and one job per step.

## Steps

1. Read the brief, the tool API file, `docs/workflow-format.md`, `docs/tools-and-code.md` and `examples/base-agent.json` (a pattern for the JSON).
2. Write `out/spec.json`: every constant the brief fixes, each with its rule number: bands and their limits, business-day counts, holidays, working days, time windows and whether the ends are included, attempt counts, floors per product type, fixed sentences, the outcome and reason table, queue names. Where the brief is unclear, take the literal reading and mark the entry `"unclear": true`.
3. Write `out/gen.py`. It reads `out/spec.json` and the tool API file and writes `out/<slot>.workflow.json` (`<slot>` is in the prompt). A constant lives in the spec once; the generator writes it everywhere it is needed. Tool URLs, fields and allowed values come from the tool API file.
4. Build the code nodes from `lib/`. `lib/cal.py` holds tested functions; `from snippets import code` (after `sys.path.insert(0, "lib")`) gives `code(body, spec_subset)`, the text of a code node that already contains `SPEC` and every helper:
   `parse_now`, `to_date`, `is_bd`, `add_bd` (the n-th business day after a date), `on_or_after_bd`, `last_bd_of_week`, `say_date`, `resolve_phrase(text, today, next_week_mode)` (customer words to a date), `hhmm_from_words`, `promise_date_state`, `callback_state`, `band_for`, `floor_for`. Read the docstrings in `lib/cal.py`. The helper text is about 9 KB: put `code(...)` only into the few code nodes that call a helper (date facts, date and time checks), and keep closing nodes as short plain snippets without it. Check that the brief's meaning of "this/next weekday", "business day" and "later than now" matches the helper; if it differs, write the variant in the spec and the body.
5. Shape the agent with these patterns:
   - **Opening:** the brief's required first sentence, word for word, as a fixed `tts` `on_enter` text. Before identity is verified, speak only what the brief allows.
   - **Facts in code:** after `get_account`, one code node works out, for each late product, its band, deadline, attempts, floor and the dates to propose, and writes them as plain sentences into a variable that the next prompt shows. The model sees one deadline per product.
   - **Customer's dates and times:** extraction fields hold the customer's words as text ("tomorrow", "the 20th", "next Friday", "eleven in the morning"). A code node turns them into a date or a time with `resolve_phrase` / `hhmm_from_words` from the call's `now`, then checks them with `promise_date_state` or `callback_state` and writes the verdict and the finished sentence the agent should say next. When the words give no date, the sentence asks for the exact day.
   - **Counters in code:** wrong answers, persuasion attempts per product, the product the call is on, and each "offer once" item. A route moves the call forward on a code or tool result.
   - **Extraction variables take only their listed values.** A code node that writes anything else to them (for example `''` to clear one) is rejected by the platform and the old value stays, so the next route sees a stale value. Give every extraction enum a neutral value such as `none` and reset to it. `tools/validate.py` reports every such write.
   - **Count each event in exactly one place.** A refusal, a human request or an unclear answer is counted either by a global (intent) node or by the step's own route, never by both. When a global node covers an event, list in its `excluded_nodes` every step that handles that event itself, including that step's counting node. Otherwise one customer sentence is counted twice (seen: one "I don't care" counted as two refusals and ended the call).
   - **Global (intent) nodes see every transition.** A global node is checked after each route, so one customer sentence can fire it again while a code node runs, and the node then returns to the previous node, which re-runs its counter. Put every non-conversation node (code, api request, end) and every step that handles the event itself in the global node's `excluded_nodes`. Handle the same event in a step that the global node excludes (for example the opening step) with its own enum value, so it is never lost.
   - **A question is not a refusal.** Give customer questions ("is this a scam?", "who is this?", "what is this about?") their own enum value, answer them with the brief's sentence, and ask again; only a real refusal moves a counter.
   - **Once-only offers:** each gets its own node whose entry is the fixed sentence; the route then moves on, so the sentence is said once.
   - **Identity:** call the verify tool with a complete answer: a full date (day, month, year) converted to the API's format, or all the digits. When the customer gave a part, ask for the rest, then call. Apply the brief's rules for wrong answers and retries in a counter.
   - **Answers that arrive in pieces:** keep what the customer has said so far in code variables (for a date of birth: day, month, year; for digits: the digits so far). After each turn merge the new piece with the old ones, call the verify tool only when the answer is complete, and ask only for the missing piece ("And the year?"). A turn that stops mid-sentence is not an answer: ask the same question again, count no attempt and no refusal, and move to refusal handling only after a clear refusal.
   - **Closing:** outcome and reason are computed in code from the call's state. A workflow-level tool with `alwaysRunsAt` at the end of the call sends them, so every path closes exactly once, as the last tool call, after the goodbye.
   - **After a tool result:** a post-hook adds one plain instruction line (`what_to_do_next`, see `docs/tools-and-code.md`): what to say now, or which tool to call next. After a failure the line gives the exact sentence to say ("There was a technical problem. I will try once more.") and the retry rule from the brief; success wording appears only after a success result.
   - **Prompts:** short, one job per node, written as a script: "Say: ... Then ask: ... When the customer answers, ..." with the fixed sentences in quotes. Add a "do not" line only for something the brief explicitly forbids.
   - **No dead ends:** every conversation node has `max_node_turns` and a `max_turn_transition`; every path reaches an `end_call` node. Leave `agent_config` out.
6. Check without network: `python3 tools/validate.py out/<slot>.workflow.json inputs/<tool_api_file>`. Fix every ERROR.
7. Check the arithmetic: write `out/scenarios.json` (format in `tools/codecheck.py`) with expected values you work out by hand from the brief: each band and its deadline, a weekend or holiday date, the days before and after a holiday, each edge of every time window, a phrase like "tomorrow" or "next Friday" resolved from `now`, the outcome of each path. Run `python3 tools/codecheck.py out/<slot>.workflow.json out/scenarios.json` and fix until it prints RESULT: PASS.
8. Save: `python3 -c "import freya,json,sys; print(json.dumps(freya.save_workflow(sys.argv[1], json.load(open(sys.argv[2])))))" <slot> out/<slot>.workflow.json`. It prints `workflow_id` and `agent_id`. The same slot updates the same workflow. Save as soon as step 6 passes, and again after each fix. If the platform answers 503, wait a minute and try again.
9. No practice customers exist in this folder, and the phone agent is tested later by others. Use the remaining time on a rule-by-rule review: write `out/coverage.json` with one entry per numbered rule of the brief naming the node or code line that carries it. Give each rule without an entry a home in the workflow, then save again.
10. Finish with one line: the `workflow_id`, the `agent_id`, and the results of the last `validate.py` and `codecheck.py` runs.

## Working rules

- Change the agent only through the file and `save_workflow`.
- Rules that must hold on every call live in code or in a route; the prompt carries the wording.
- Keep your own files in `out/`.
