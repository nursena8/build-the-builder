---
name: build-phone-agent
description: Build a Freya phone agent from a bank's brief and tool API, check it offline and save it. Use when asked to build a phone agent from a brief.
---

# Build a phone agent from a brief

Work only inside the current folder. Everything you need is here: the brief and the tool API file under `inputs/`, `docs/`, `examples/base-agent.json`, `freya.py`, `tools/validate.py`, `tools/codecheck.py`.
Nobody will answer questions. Never ask one and never end your turn to wait. Never look outside this folder.
The brief and the tool API file you were given are the only source of facts. Do not use numbers, dates, names or rules from any example, from these instructions or from your memory of other briefs.
You have a fixed time budget (given in the prompt). Save a working agent early, then improve it.

## Steps

1. Read the brief, then the tool API file, then `docs/workflow-format.md`, `docs/tools-and-code.md` and `examples/base-agent.json` (a pattern for the JSON, not the answer).
2. Write `out/spec.json` first. List every constant the brief fixes: thresholds, bands, business-day counts, holidays, working hours and whether their ends are inclusive, attempt counts, fixed sentences, floors, the outcome and reason table, queue names. Give each entry the brief's rule number. Mark anything unclear and take the literal reading.
3. Write a generator `out/gen.py` that reads `out/spec.json` and the tool API file and writes `out/<slot>.workflow.json` (`<slot>` is the slot name from the prompt). A constant lives in the spec once; the generator writes it into the code and the prompts. Tool URLs, fields and allowed values come from the tool API file.
4. Build the agent from these patterns:
   - **Opening:** the brief's required first sentence, word for word, as a fixed `tts` `on_enter` text. Say nothing the brief forbids before identity is verified.
   - **Facts in code:** after `get_account`, a code node computes, for each late product, its band, its deadline, its number of persuasion attempts, its floor, and the dates the brief says to propose. Give the model one finished fact per product. Never give the model two possible deadlines and let it choose.
   - **Counters in code, not in the prompt:** wrong answers, persuasion attempts per product, "offer only once" items, the product the call is on. Move to the next step on a code or tool result, not on what the customer says.
   - **Identity:** call the verify tool only with a complete answer (a full date with day, month and year, converted to the format the API wants; all digits of a number). If the customer gave a part, ask for the rest first. Follow the brief for wrong answers and retries.
   - **Outcome and reason in code:** compute them from the state of the call and run the closing tool from a workflow-level tool with `alwaysRunsAt` at the end of the call, so every path closes exactly once and the closing tool is the last tool call. Say goodbye before it.
   - **Tool failures:** the agent says there was a problem, follows the brief's retry rule, and never says something was recorded, saved or booked unless the tool returned success.
   - **One plain instruction line after every tool result** (post-hook `what_to_do_next`, see `docs/tools-and-code.md`) so the model speaks after each result and does not ignore a negative one.
   - **No dead ends:** set `max_node_turns` with a `max_turn_transition` on every conversation node. Every path must reach an `end_call` node. Leave `agent_config` out.
5. Check without network: `python3 tools/validate.py out/<slot>.workflow.json inputs/<tool_api_file>`. Fix every ERROR.
6. Check the arithmetic: write `out/scenarios.json` (format in `tools/codecheck.py`) with expected values you work out by hand from the brief: each band and its deadline, a date on a weekend or holiday, the last day before and after a holiday, each edge of a time window, the outcome for each path. Do not copy expected values from your own code. Run `python3 tools/codecheck.py out/<slot>.workflow.json out/scenarios.json`. Fix the code or the spec until it passes.
7. Save: `python3 -c "import freya,json,sys; print(json.dumps(freya.save_workflow(sys.argv[1], json.load(open(sys.argv[2])))))" <slot> out/<slot>.workflow.json`. It prints `workflow_id` and `agent_id`. The same slot updates the same workflow. Save once as soon as step 5 passes, and again after each fix. If the platform answers 503, wait a minute and try again.
8. There are no practice customers. Do not run `tools/run_cases.py`, do not look for a test set, and do not call the bank's tools yourself. Spend the remaining time re-reading the brief rule by rule against the workflow: for each numbered rule, name the node or code line that carries it, and fix any rule that has none.
9. Finish with one line: the `workflow_id`, the `agent_id`, and the result of the last `validate.py` and `codecheck.py` runs.

## Rules

- Never edit the agent on the platform by hand. Change the file and save it again.
- A rule that must hold on every call belongs in code or in a route, not only in a prompt.
- Keep the spec and the generator in `out/`. Do not write outside `out/` except through `freya.py`.
