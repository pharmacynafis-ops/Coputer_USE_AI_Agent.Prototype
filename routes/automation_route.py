from typing import Dict, Any
from automation.sandbox_runner import sandbox_executor


def handle_segment(segment: Dict[str, Any], session_context: Dict[str, Any], executor=None) -> Dict[str, Any]:
    """Automation route skeleton.

    For safety this skeleton will only execute when an `executor` is explicitly
    provided. It collects outputs per step.
    """
    steps = segment.get("steps", [])
    if executor is None:
        return {"route": "automation", "planned_steps": steps}

    outputs = []
    for step in steps:
        tool = step.get("tool")
        args = step.get("arguments", {})
        try:
            if executor is None:
                out = sandbox_executor(tool, args)
            else:
                out = executor(tool, args)
        except Exception as e:
            out = f"Error: {e}"
        outputs.append({"step": step, "output": out})
    return {"route": "automation", "outputs": outputs}
