## 03 — Request Classifier Design

Goal: design a production-grade classifier that maps incoming user prompts into the target categories with confidence scores and well-defined fallback behavior. All integration points reference existing code evidence.

Existing evidence
- `SmartThinking.should_skip_thinking` is invoked at the top of `/stream` to decide SKIP vs NEED_AGENT ([smartThinking.py], [server.py]). This demonstrates a current lightweight classification/hinting stage but only for fast-path skip behavior.
	- Evidence: `skip, quick_reply_text = smart.should_skip_thinking(user_prompt, recent_history)` in [server.py](server.py#L416) and `def should_skip_thinking(...)` in [smartThinking.py].

Design
1) Classification categories
 - chat
 - knowledge
 - analysis
 - development
 - automation
 - security
 - debug
 - research

2) Confidence scoring
 - Classifier returns `category` and `confidence` (float 0.0–1.0).
 - Thresholds: high >= 0.85, medium 0.6–0.85, low < 0.6.

3) Fallback behavior
 - If `high` confidence: route directly to Task Router with that category hint.
 - If `medium` confidence: include classifier hint but run `StepsPlanner` in a restricted mode (no destructive commands) and consult `task_router` for final decision.
 - If `low` confidence: ask a short clarifying question or route to Chat Route asking for clarification.

4) Ambiguous request handling
 - When multiple categories have similar scores (delta < 0.08), return `ambiguous` with top-N candidates and `confidence` for each. Task Router can run a lightweight multi-route execution or ask user clarification.

5) Misclassification recovery
 - All routes must support idempotent handoff: if execution fails or `ContextOwner.is_stuck` triggers, Task Router must be able to switch to another route (e.g., from Development -> Debug or Research) and `StepsPlanner.refine_plan` must be invoked.
 - Evidence: `planner.refine_plan(...)` and `context_owner.is_stuck(...)` in [server.py] are existing hooks for recovery.

6) Classifier implementation options
 - Heuristic-first model: implement deterministic rules for: greetings, file/command patterns (words like `create file`, `mkdir`, drive-letter paths), question words (`why`, `how`) to map to categories; fall back to an LLM scoring model for ambiguous cases.
 - LLM scoring model: prompt LLM with categories and ask for classification + confidence (use same `OpenAI` client used in `SmartThinking` / `StepsPlanner`).

7) Exact integration points into CompLoca
 - Replace/augment current `smart.should_skip_thinking` call in `/stream` ([server.py](server.py#L416)) with:
	 - `classification = request_classifier.classify(user_prompt, recent_history)`
	 - If `classification.category == 'chat' and classification.confidence >= 0.85` -> call Chat Route (or `smart.quick_reply` for backward compat).
	 - Otherwise pass `classification` into `task_router.route(user_prompt, classification, session_id, context)` and let router decide whether to call `StepsPlanner` or direct route handlers.

8) Data contracts
 - `classify(prompt, context) -> { category: str, confidence: float, candidates?: [{category,confidence}] }`

9) Logging and telemetry
 - Persist classifier outputs along with each session (save to `steps_log.json` or `chat_history.json`) for traceability.

10) Testing and validation
 - Unit tests for heuristics; A/B validation of LLM scoring; keep fallback to `smart.should_skip_thinking` until classifier is validated in production.

Files to add/modify
 - Add: `request_classifier.py` (classifier implementation and test harness)
 - Modify: `server.py` `/stream` to call the classifier and route via `task_router` instead of directly invoking planner for all prompts.

Traceability: Integration points and recovery hooks exist in [server.py](server.py#L416-L436, server.py#L486-L506) and `SmartThinking`/`StepsPlanner` implementations.
