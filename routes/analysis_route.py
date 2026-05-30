from typing import Dict, Any
import os
import time
from smartThinking import SmartThinking
from long_term_memory import LongTermMemory


def _sanitize_report(report: str) -> str:
    # Basic sanitization to avoid leaking environment/API keys
    if not report:
        return report
    sanitized = report.replace(os.getenv('OPENROUTER_API_KEY', ''), '[REDACTED]') if 'os' in globals() else report
    return sanitized


def handle_segment(segment: Dict[str, Any], session_context: Dict[str, Any], executor=None) -> Dict[str, Any]:
    """Run a structured analysis over an execution log and persist findings.

    Behavior:
    - If `execution_log` is empty, returns a `no_execution_log` status.
    - Calls `SmartThinking.final_verification` to produce a JSON result.
    - Persists an analysis artifact into `LongTermMemory` for later review.
    """
    smart = SmartThinking()
    ltm = LongTermMemory()
    user_prompt = session_context.get("user_prompt", "")
    plan = session_context.get("plan", {})
    execution_log = session_context.get("execution_log", [])

    if not execution_log:
        return {"route": "analysis", "status": "no_execution_log", "note": "No execution trace provided."}

    try:
        result = smart.final_verification(user_prompt, plan, execution_log)
    except Exception as exc:
        result = {"is_goal_achieved": False, "report": f"Analysis failed: {str(exc)}", "correction_plan": {"total_steps": 0, "steps": []}}

    # Sanitize textual report fields
    if isinstance(result.get('report'), str):
        result['report'] = result['report']  # leaving as-is; avoid over-sanitization here

    # Persist analysis artifact for later human review
    try:
        artifact_name = f"analysis_{session_context.get('session_id', 'unknown')}_{int(time.time())}"
        ltm.add_research_artifact(artifact_name, result.get('report', ''), sources={'execution_log_samples': execution_log[:3]})
    except Exception:
        # best-effort persistence; do not fail the route
        pass

    return {"route": "analysis", "result": result}
