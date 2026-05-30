# Chat Context Failure Audit

## Executive Summary

This audit examines why the project's chat system fails to resolve follow-up references (e.g., user: "why" after assistant: "there are no executable steps"). Root causes are architectural: session continuity is not preserved across requests, immediate assistant responses are not persisted into short-term conversation state when the pipeline short-circuits, and a planning-first pipeline treats nearly every input as a task planning request rather than a conversational turn. The result: follow-ups with pronouns or single-word clarifications have no local context to resolve, so the model is asked an ambiguous question and responds with a clarification request.

## Root Causes (summary)

- Missing session continuity in the `/stream` API: no acceptance of a client-provided `session_id` to continue an existing session; server always calls `context_owner.start_session(...)` and begins a fresh session per request.
- Short-circuit when `StepsPlanner` returns zero steps: controller yields a final string and returns early, without saving assistant reply into session or long-term memory; thus the assistant's output is not available for follow-ups.
- LongTermMemory is only a high-level summary: `LongTermMemory.get_context_for_prompt()` returns user profile and historical summaries (project history, files, agent identity) but not the most recent assistant or user messages, so it cannot support immediate coreference.
- Pipeline design routes all inputs through a task planner (`StepsPlanner`) and task execution flow rather than a conversational chat handler; single-token follow-ups are interpreted as new, isolated prompts.
- No explicit reference-resolution / coreference expansion layer that rewrites pronouns like "why" to the target utterance (e.g., "why did you say there are no executable steps?").
- System prompt + planner instructions bias the system toward being stateless and task-oriented (the architecture focuses on generating plans and executing tools, not continuing conversational state).
- Session lifecycle saving occurs only at the end of successful flows (`context_owner.save_conversation_to_session()`), and is skipped when the flow returns early (e.g., when `total_steps == 0`).
- The server returns a `session_id` in the stream but does not accept it in subsequent requests, nor does the client-side appear required to provide it back to the server for continuing context.

## Affected Files (key)

- [server.py](server.py) — stream handler, session creation, plan orchestration, early return when `total_steps == 0`.
- [context_owner.py](context_owner.py) — session management, `start_session()`, `conversation_history`, `save_conversation_to_session()`.
- [long_term_memory.py](long_term_memory.py) — `get_context_for_prompt()` returns high-level summaries rather than raw recent messages.
- [steps_planner.py](steps_planner.py) — enforces strict planning-first rules, instructs `total_steps = 0` for conversational inputs.
- [smartThinking.py](smartThinking.py) — quick-skip detection (`should_skip_thinking`) that can bypass agent reasoning and reply without integrating session state.
- [dynamic_tool_loader.py](dynamic_tool_loader.py) — not directly responsible for context loss, but contributes to complexity of tool metadata in system-level prompt.

## Architectural Weaknesses (explanation)

- Stateless request handling: `/stream` treats each incoming `prompt` as an independent request, creating a new session via `context_owner.start_session()` on every call (server.py: stream start). The server emits a `session_start` but does not provide a way to resume that session from the client (no `session_id` param accepted on new requests).

- Early-return path erases conversation: server.py logic:
  - `plan = planner.create_plan(enhanced_prompt)`
  - `if plan.get("total_steps", 0) == 0: yield final message; return`
  This path returns before `context_owner.save_conversation_to_session()` is ever reached. Therefore the assistant's own reply is not written to session or memory for later reference.

- In-memory session vs long-term memory mismatch: `ContextOwner.conversation_history` is the place where per-session turns are collected, but `LongTermMemory.get_context_for_prompt()` purposefully composes a high-level summary (user profile, last interactions). There is no code that automatically merges the *current* session buffer into the prompt passed to the planner or to the conversational agent unless the session has been saved to long-term memory.

- Planning-first pipeline: every prompt is funneled into `StepsPlanner.create_plan(...)` (server.py), which is designed for tool execution. Human conversational clarifications ("why") are outside the planner's remit. Because the planner's instruction says "If the request does not require tools (greeting), set `total_steps = 0`", the server treats such outputs as terminal: it reports "no steps" and stops—without creating a proper natural-language assistant reply that is stored for context.

- Missing conversational agent invocation: an Agent instance exists (`Agent[None, AgentResponse]` in `server.py`) but the `/stream` routine does not call that agent to generate natural-language replies in the common case. Instead the planner and executor produce execution traces; natural-language fallback behavior is fragmented among `smartThinking.quick_reply`, `should_skip_thinking`, and ad-hoc `yield` strings.

- No explicit coreference handling: nothing in the pipeline rewrites a follow-up such as "why" into a disambiguated prompt referencing the last assistant message. The system expects the model to perform that implicit resolution, but the model is not given the necessary recent assistant message in the effective prompt.

## Evidence from Code (citations)

- server.py: session creation and enhanced prompt assembly
  - context owner session start: `session_id = context_owner.start_session(user_prompt)` (server.py — stream)
  - historical context assembly: `historical_context = long_term_memory.get_context_for_prompt(user_prompt)` and `enhanced_prompt = f"{historical_context}\n\n## طلب المستخدم الحالي:\n{user_prompt}"` (server.py — stream)
  - plan invocation and early return: `plan = planner.create_plan(enhanced_prompt)` followed by `if plan.get("total_steps", 0) == 0: yield ...; return` (server.py — stream). This `return` prevents saving the assistant message and terminates the flow.

- context_owner.py: session lifecycle
  - `start_session()` creates `self.session_id` and appends the initial user prompt into `self.conversation_history`, but there is no external `resume_session(session_id)` method used by the `/stream` endpoint to attach a new incoming prompt to an existing session.
  - `save_conversation_to_session()` exists but is only called at the bottom of the main execution flow after tasks finish — it is unreachable in early-return cases.

- long_term_memory.py: context generation
  - `get_context_for_prompt()` builds a fact-style summary (user profile, stats, last 3 project_history items, files created, agent identity, and friendly instructions). It does not pull in the live `ContextOwner.conversation_history` unless that was already persisted into `project_history` or `user_profile`.

- steps_planner.py: task-first instructions
  - Planner prompt enforces `If the request does not need tools (greeting, simple question), set total_steps = 0.` The planner is therefore used as the primary interpreter of all prompts, and the server treats `total_steps == 0` as a final, non-conversational outcome.

- smartThinking.py: quick-skip logic that returns a reply without integrating session state
  - `should_skip_thinking()` asks the model whether to SKIP or NEED_AGENT and can return a `reply` that is directly used by the server to stream an early response. This method uses only `user_prompt` and does not reference the prior assistant message nor session buffer.

## Evidence from Runtime Flow (how the bug manifests)

Replaying the failing sequence against the code yields the failure mode:

1. User sends: "can you do something on my Computer OR these info are unreal and you can do nothing ?"
   - `/stream` starts a new session: `start_session(user_prompt)`.
   - `historical_context = long_term_memory.get_context_for_prompt(user_prompt)` — returns only summary info.
   - `enhanced_prompt` (summary + current prompt) sent to `StepsPlanner.create_plan()`.
   - Planner determines `total_steps = 0` (because the planner judged the user's request as not actionable), so server yields `'لا توجد خطوات للتنفيذ.'` and returns early. `context_owner.save_conversation_to_session()` is not called.
   - The assistant's reply is thus ephemeral and not persisted anywhere accessible to subsequent requests.

2. User sends a follow-up: "why"
   - `/stream` again starts a new session (fresh `context_owner.start_session('why')`), `historical_context = long_term_memory.get_context_for_prompt('why')` — which is a generic profile summary and does not include the ephemeral answer produced above.
   - Planner receives the new short prompt and no assistant context. The model cannot resolve the pronoun reference and the planner / smartThinking request a clarification from the user.

Result: the assistant asks for clarification rather than explaining the previous assistant statement.

## Conversation-State Failures (detailed)

- No durable short-term conversation buffer is passed into inference for follow-ups. The system has two state stores:
  - `ContextOwner.conversation_history` (session-local, in-memory until saved);
  - `LongTermMemory` (durable, summarized). Neither is used to provide raw, recent-turn messages to the planner or the agent at the time of inference.

- The server does not accept a continuing `session_id` from the client to attach future prompts to the existing `ContextOwner` instance. `context_owner.start_session()` is always used, creating a fresh session context.

- Because the assistant reply in the failing case is produced as an immediate stream string and the flow returns early, the assistant's reply is not appended to any durable store prior to returning.

## Reference-Resolution Failures (examples)

- Pronouns like "why" rely on preceding assistant text. There is no step that creates a disambiguated user prompt such as: "Why did you say 'there are no executable steps'?" No canonical rewrite or coreference expansion step exists.

- There is no mechanism to (a) detect that the incoming prompt is a follow-up to a prior unfinished session, (b) fetch recent assistant/user messages for that session, and (c) prepend them to the model prompt before asking the model to resolve the follow-up.

- Planner-first design and quick-skip logic expect the model to handle pragmatic inference on a single short prompt, which is brittle for one-word follow-ups.

## Personality Failures

- Lack of continuity: because session continuity is not preserved, the agent appears context-blind and robotic; follow-up questions are treated as new unrelated inputs.

- System prompt content (in `server.py` where `final_system_prompt` is assembled) is strongly tool- and plan-oriented and contains rigid rules about output format. This encourages the model to behave as a deterministic planner rather than a conversational partner. Human-like continuity is sacrificed for structured tooling behavior.

## Planning-System Failures

- The planner is the gateway for all user inputs. For short clarifying utterances, `StepsPlanner` is the wrong component to call first. The server assumes that `total_steps == 0` means "no actionable work" and immediately terminates the conversation without producing a stored assistant reply suitable for follow-ups.

- The `smartThinking.should_skip_thinking()` function can short-circuit the pipeline and produce a direct reply without integrating session context.

- The code flow lacks a clear separation between "task mode" (planning + execution) and "chat mode" (conversational continuations). The system attempts to be both simultaneously but without an orchestration layer to choose appropriately.

## Recommended Architectural Solution (high-level, non-invasive)

These recommendations are architectural guidance only — do NOT implement changes in this audit.

1. Session Continuity API
   - Make session lifecycle explicit in the API: accept an optional `session_id` in `/stream` (and other endpoints) so clients can continue a previous session. When a client does not provide `session_id`, create one and return it; when provided, resume that session's `ContextOwner` buffer.

2. Persist assistant replies immediately for short-turns
   - Avoid early-return paths that produce ephemeral assistant text without saving it. If the pipeline decides to short-circuit (e.g., `total_steps == 0`), ensure the produced textual assistant reply is appended to `ContextOwner.conversation_history` and persisted (or at minimum kept available to the same session) before returning.

3. Two-tier context assembly
   - Compose prompts from (A) recent raw conversation turns (e.g., last N messages within `ContextOwner.conversation_history`) and (B) long-term summary (`LongTermMemory`). Recent raw turns are required for correct pronoun/coref resolution.

4. Separate Chat vs Planner flows
   - Add an orchestration layer that classifies whether the incoming prompt is a conversational follow-up, a planning request, or a tool action request. For follow-ups/questions about previous assistant replies, route to a chat handler that uses the recent-turn buffer and the agent (`Agent` instance) for natural-language responses.

5. Coreference Expansion Layer
   - Implement a small rewrite step for single-token follow-ups and pronouns: if a prompt looks like a follow-up (e.g., `why`, `what`, `who`, `that`, `it`), expand it into an explicit question using the last assistant message: e.g., `"why"` → `"Why did you say: 'there are no executable steps' ?"`. This can be implemented as a deterministic expansion that uses the most recent assistant message from `ContextOwner.conversation_history`.

6. Improve planner integration
   - Use planner only when the orchestration layer determines the prompt is an actionable task request. If planner returns `total_steps == 0`, still call the chat handler to generate a human-friendly explanation of why the planner judged the request as non-actionable, then persist that assistant message.

7. Instrumentation and Trace Logging
   - Add detailed logs when sessions are created/resumed, when planner returns `total_steps == 0`, and when assistant replies are produced but not persisted. This will make reproducing and debugging follow-up failures straightforward.

8. Avoid brittle system-prompt rules for general conversation
   - Keep the system prompt used for task planning separate from the one used for chat. The planner prompt should remain structured; the chat prompt should prioritize conversational continuity and scale down strict formatting requirements.

## Minimal Code Evidence Snippets (for developers)

- server.py (stream): plan generation and early return

  - `historical_context = long_term_memory.get_context_for_prompt(user_prompt)`
  - `enhanced_prompt = f"{historical_context}\n\n## طلب المستخدم الحالي:\n{user_prompt}"`
  - `plan = planner.create_plan(enhanced_prompt)`
  - `if plan.get("total_steps", 0) == 0: yield ...; return`

- context_owner.py: session start and save

  - `self.session_id = str(uuid.uuid4())[:8]` (start_session)
  - `self.conversation_history.append({"role": "user", "content": user_prompt, ...})` (start_session)
  - `save_conversation_to_session()` called at the end of the main flow, but not on early return.

- long_term_memory.py: high-level summary in get_context_for_prompt

  - returns profile, last 3 project_history items, files_created and agent identity — no raw recent-turn messages.

## Conclusion

The failure to answer follow-up pronoun questions (e.g., "why") is caused by the pipeline's session/statelessness and planning-first architecture. The system does not reliably provide the model with the immediately preceding assistant message(s) nor does it keep the per-session conversation buffer available for follow-up inference. Fixing this requires introducing explicit session continuation, ensuring assistant replies are persisted (even for early-return planner outcomes), and separating conversational handling from planning/execution. Implementing a small coreference expansion step for single-token follow-ups will provide immediate relief while the larger architectural changes are planned.

---

Audit prepared by: Senior AI Agent Architect (analysis only). 

(End of report)
