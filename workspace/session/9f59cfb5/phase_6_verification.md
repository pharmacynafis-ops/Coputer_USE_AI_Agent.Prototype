# Phase 6 Verification

This document contains human-testable verification steps for Phase 6 (Analysis, Debug, Research agents and tooling).

For each implemented requirement provide: objective, steps, input, expected output, failure indicators.

---

**1) Analysis route: run verification and produce correction plan**

- Test objective: Verify `/routes/analysis_route.py` produces a structured analysis and persists an artifact.
- Steps:
  1. Create a small `execution_log` file with a failed step (e.g., write_file failed due to permission).
  2. Call the route handler from a Python REPL or run a minimal script that imports `routes.analysis_route.handle_segment` and passes a `session_context` containing `user_prompt`, `plan`, `execution_log`, and `session_id`.
- Input: session_context with failing execution_log (one item).
- Expected output: A dict with keys `route` and `result` where `result` is a JSON-like dict containing `is_goal_achieved`, `report`, and possibly `correction_plan`.
- Failure indicators: handler raises exception; `result` missing `is_goal_achieved`; no artifact created under `memory/long_term/research/`.

---

**2) Debug route: summarize failures and generate a help question**

- Test objective: Verify `/routes/debug_route.py` detects failures, generates a human-help question, and persists a debug artifact.
- Steps:
  1. Prepare a `session_context` with an `execution_log` containing at least one failed step (success=false).
  2. Import and call `routes.debug_route.handle_segment(segment, session_context)`.
- Input: `execution_log` with at least one failed step.
- Expected output: dict with `route` == "debug", `failures` list, `summary` and `question` (string). Also a file saved in `memory/long_term/research/` with a `debug_` prefix.
- Failure indicators: no `question` returned, no research artifact file created.

---

**3) Research route: persist research intent when connectors absent**

- Test objective: Verify `/routes/research_route.py` returns `evidence_not_found` when no `EXTERNAL_SEARCH_API_KEY` is configured and saves an artifact.
- Steps:
  1. Ensure `EXTERNAL_SEARCH_API_KEY` is not set in the environment.
  2. Call `routes.research_route.handle_segment(segment, session_context)` with `user_prompt` containing a research query.
- Input: `user_prompt` string, `session_id`.
- Expected output: dict with `status` == `evidence_not_found` and `intended_query` echoing the prompt. A file under `memory/long_term/research/` with `research_intent_` prefix should exist.
- Failure indicators: handler errors; no artifact file created.

---

**4) Integration sanity: server `/stream` preserves behavior with routes**

- Test objective: Run a short scenario using the existing `/stream` flow that triggers analysis or debug.
- Steps:
  1. Start the Flask server: `python server.py`.
  2. Send a request to `/stream?prompt=...` that leads to an actionable plan which includes at least one failing step (e.g., attempt to write to a protected path).
  3. Observe SSE events (step_result, need_help, final_failure, plan, final_success).
- Input: HTTP request to `/stream` with crafted prompt.
- Expected output: SSE events emitted. If a failure is detected and stuck logic triggers, an SSE event of type `need_help` should be sent. After analysis, a `final_failure` or `final_success` event occurs.
- Failure indicators: server crashes, no `need_help` when repeated failures occur, or no final verification call.

---

Notes:
- These steps are designed to be executed by a non-developer using simple Python calls or the running server.
- Artifact files are saved under `memory/long_term/research/` and should be inspected for content and timestamps.

---

Phase verification author: Automated implementation for Phase 6.
