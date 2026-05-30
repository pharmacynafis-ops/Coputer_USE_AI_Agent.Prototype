from typing import Dict, Any
from context_owner import ContextOwner
from long_term_memory import LongTermMemory
import time


def handle_segment(segment: Dict[str, Any], session_context: Dict[str, Any], executor=None) -> Dict[str, Any]:
    """Debug handler: summarize recent failures and generate a user-help question.

    Responsibilities:
    - Identify failed steps in `execution_log`.
    - Use `ContextOwner.generate_help_question` to create an actionable question for the user.
    - Persist a debug artifact to long-term memory for auditing.
    """
    execution_log = session_context.get("execution_log", [])
    failures = [e for e in execution_log if not e.get("success", True)]
    if not failures:
        return {"route": "debug", "status": "no_failures"}

    # Use the most recent failure to build the help question
    last_failure = failures[-1]
    step = {
        "step_number": last_failure.get("step_number"),
        "description": last_failure.get("description"),
        "tool": last_failure.get("tool")
    }
    error_message = last_failure.get("result", "")

    # Build a ContextOwner for memory search (best-effort local view)
    co = ContextOwner()
    memory_search = co.search_memory(step.get("description", ""))
    question = co.generate_help_question(step, error_message, memory_search)

    # Persist debug artifact
    try:
        ltm = LongTermMemory()
        artifact_name = f"debug_{session_context.get('session_id', 'unknown')}_{int(time.time())}"
        ltm.add_research_artifact(artifact_name, question, sources={"failure_sample": last_failure})
    except Exception:
        pass

    summary = f"{len(failures)} failed steps; latest step {step.get('step_number')}"
    return {"route": "debug", "failures": failures, "summary": summary, "question": question}
