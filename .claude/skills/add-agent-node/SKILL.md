---
name: add-agent-node
description: Add or rename a node in the ProcureGPT LangGraph procurement graph. Use whenever the task involves adding/removing/renaming an agent step (a graph node), because the node name must be kept in sync across four places or the workspace UI and progress bar silently break.
---

# Adding / renaming a LangGraph node in ProcureGPT

The procurement graph is one compiled `StateGraph`, but a node's name is
referenced in **four** places. Miss one and the node runs but the UI shows the
wrong step / progress / agent label, or the step never appears.

## The four sync points

1. **`backend/app/agents/nodes/<node>.py`** — the node function itself. Signature:
   `async def my_node(state: ProcurementState) -> dict:` returning a *partial*
   state update (never the whole state). If it makes an LLM call, use
   `llm_client.generate()/generate_json()` — never a provider SDK directly, so
   token tracking + retries + prompt caching all apply for free.

2. **`backend/app/agents/orchestrator.py`** — register it:
   - `workflow.add_node("my_node", my_node)`
   - wire edges (`add_edge` / `add_conditional_edges`). If it's a human/email
     wait point, add it to `interrupt_before` / `interrupt_after` in
     `init_procurement_graph()`.

3. **`backend/app/workflows/session_workflow.py`** — add the node name to BOTH:
   - `STEP_PROGRESS_MAP` (int 0–100, monotonic with flow order)
   - `STEP_AGENT_MAP` (the UI "agent" label, e.g. `"Vendor Agent"`)
   - and, if it should post a chat line, `_node_message()` / `_emit_event()` titles.

4. **`backend/app/api/v1/workflows.py`** — add it to `WORKFLOW_STEPS_TEMPLATE`
   (the ordered step list the frontend renders as the workflow tree).

## Checklist

- [ ] Node function returns a partial `dict`, reads only from `state`.
- [ ] Registered in `orchestrator.py` with edges wired.
- [ ] `STEP_PROGRESS_MAP` + `STEP_AGENT_MAP` updated (both).
- [ ] `WORKFLOW_STEPS_TEMPLATE` updated, same order.
- [ ] If it's a pause point, added to the interrupt list.
- [ ] Ran `python -m scripts.check_workflow` to confirm ordering is consistent.

## Gotcha

`current_step` in the returned dict is what the UI keys on — set it to the node
name. Merged nodes (`parse_request`, `ocr_extract`) override `current_step` to
the merged name even though they call several sub-functions; follow that pattern
if you compose multiple steps into one graph node.
