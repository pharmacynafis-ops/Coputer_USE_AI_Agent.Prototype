## Chat Route — Implementation Document

1. Purpose
 - Provide conversational responses for user prompts that do not require tool execution or system-side actions.
 - Accept simple Q&A, follow-ups, and free-form chat.

2. Inputs
 - `user_prompt` (string) from SSE `/stream` or HTTP API.
 - Context: `LongTermMemory.get_context_for_prompt(user_prompt)` and recent `chat_history`.
 - Evidence: `historical_context = long_term_memory.get_context_for_prompt(user_prompt)` in [server.py](server.py#L430) and `quick_reply` used when planner returns zero steps in [server.py](server.py#L444).

3. Outputs
 - Natural language reply JSON event (`type: final`) or `final_success`/`final_failure` with `report`.
 - Evidence: SSE yield `{'type': 'final', 'message': assistant_reply}` in [server.py](server.py#L445).

4. Decision criteria
 - If `StepsPlanner.create_plan` returns `total_steps == 0` the system currently falls back to `smart.quick_reply` (chat behavior).
 - Evidence: `if plan.get("total_steps", 0) == 0: assistant_reply = smart.quick_reply(...)` in [server.py](server.py#L444).

5. Required agents
 - Chat agent using LLM client (re-use `SmartThinking.quick_reply` or a new `chat_agent` wrapper around OpenAI/OpenRouter client).

6. Required tools
 - None for pure chat; read-only access to `LongTermMemory`.

7. Required prompts
 - System prompt that includes `LongTermMemory` context and `conversation_context` (already composed as `enhanced_prompt` in [server.py](server.py#L426)).

8. State transitions
 - Entry: routed to Chat Route by classifier/task router.
 - Action: generate reply via chat agent.
 - Persist: append assistant reply to `ContextOwner.conversation_history` and optionally `LongTermMemory.update_interaction`.
 - Evidence: code path in [server.py](server.py#L444-L455) persists assistant reply.

9. Failure handling
 - If LLM call fails, return safe fallback message (`"لا توجد خطوات للتنفيذ."` currently used).
 - Evidence: exception handling around `smart.quick_reply` in [server.py](server.py#L446).

10. Retry handling
 - Minimal: retry LLM call once, escalate to user clarification if repeated failures.

11. Cost considerations
 - Keep max_tokens and temperature conservative for chat replies (see `SmartThinking` settings using `model = "openai/gpt-4o-mini"`).

12. Performance considerations
 - Cache recent chat context and rate-limit classifier calls to avoid repeated LLM invocations.

13. Security considerations
 - Chat route must not execute tools. Ensure Task Router routes only to Chat when `total_steps == 0` or classifier confidence is high for chat.

14. Integration points
 - `server.py` `/stream` route where planner currently decides; replace in future with `task_router` call to `chat_route.handle()`.

15. Required code modifications
 - Add `routes/chat_route.py` with `handle(user_prompt, session_id, context)` that returns assistant reply and events.
 - Modify `server.py` to call `task_router.route()` and let `task_router` call `chat_route`.
 - Keep current quick-reply fallback by calling `SmartThinking.quick_reply` from the new chat handler for backward compatibility.

Traceability: All behavioral recommendations above are supported by the existing fallback path in [server.py](server.py#L444-L455) and the `SmartThinking` implementation in [smartThinking.py](smartThinking.py#L1).

