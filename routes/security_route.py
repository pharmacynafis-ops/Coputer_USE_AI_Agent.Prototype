from typing import Dict, Any


def handle_segment(segment: Dict[str, Any], session_context: Dict[str, Any], executor=None) -> Dict[str, Any]:
    """Security skeleton: perform static checks on planned steps.

    This skeleton performs conservative rule checks and returns allow/deny per step.
    """
    steps = segment.get("steps", [])
    results = []
    forbidden_patterns = ["rm -rf", "--force", "shutdown", "reboot"]
    for step in steps:
        tool = step.get("tool")
        args = str(step.get("arguments", {}))
        deny = any(p in args for p in forbidden_patterns)
        results.append({"step": step, "allowed": not deny, "reason": "forbidden pattern" if deny else "ok"})
    return {"route": "security", "results": results}
