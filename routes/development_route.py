from typing import Dict, Any

from decomposer.simple_decomposer import decompose_segment
from builders.runner import run_steps
from reviewers.lint_and_test import review_execution
from long_term_memory import LongTermMemory
from smartThinking import SmartThinking


def handle_segment(segment: Dict[str, Any], session_context: Dict[str, Any], executor=None) -> Dict[str, Any]:
    """Development route implementation.

    Workflow:
    - Decompose high-level segment into atomic steps
    - If no `executor` provided, return the planned (decomposed) steps
    - Run builder to execute steps via provided `executor` (usually execute_tool_backend)
    - Run reviewer checks (syntax/tests)
    - Collect evidence into LongTermMemory and run final verification via SmartThinking
    """
    # Ensure segment has steps
    planned = decompose_segment(segment)

    if executor is None:
        return {"route": "development", "planned_steps": planned}

    # Execute build steps
    execution_log = run_steps(planned, executor)

    # Record created files into long-term memory (if any)
    ltm = LongTermMemory()
    session_id = session_context.get("session_id")
    for entry in execution_log:
        step = entry.get("step", {})
        result = entry.get("result", "")
        if step.get("tool") == "write_file":
            path = step.get("arguments", {}).get("path")
            content = step.get("arguments", {}).get("content", "")
            try:
                ltm.add_file_record(path, content, session_id=session_id)
            except Exception:
                pass

    # Run reviewer checks
    review_result = review_execution(execution_log, executor=executor)

    # Final decision via SmartThinking
    smart = SmartThinking()
    user_prompt = session_context.get("user_prompt", "")
    plan = session_context.get("plan", segment)
    try:
        final = smart.final_verification(user_prompt, plan, execution_log)
    except Exception:
        final = {"is_goal_achieved": False, "report": "final_verification failed"}

    return {
        "route": "development",
        "execution_log": execution_log,
        "review": review_result,
        "final_verification": final,
    }
