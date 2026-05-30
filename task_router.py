from typing import List, Dict, Any

# Simple Task Router (Phase 2 skeleton)
# This module provides a conservative grouping of plan steps into route segments.
# It does not execute steps; handlers are provided in `routes/` and are skeletons.

TOOL_ROUTE_MAP = {
    "write_file": "development",
    "read_file": "knowledge",
    "execute_command": "automation",
}


def map_tool_to_route(tool_name: str) -> str:
    return TOOL_ROUTE_MAP.get(tool_name, "analysis")


def route_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Group contiguous steps by route and return a route_plan structure.
    """

    route_plan = {"segments": []}
    steps = plan.get("steps", []) if plan else []
    if not steps:
        # No steps -> chat/knowledge depending on metadata
        return {"segments": [{"route": "chat", "steps": []}], "original_plan": plan}

    current_route = None
    current_segment = None
    for step in steps:
        tool = step.get("tool", "none")
        r = map_tool_to_route(tool)
        if r != current_route:
            if current_segment:
                route_plan["segments"].append(current_segment)
            current_segment = {"route": r, "steps": [step]}
            current_route = r
        else:
            current_segment["steps"].append(step)

    if current_segment:
        route_plan["segments"].append(current_segment)

    route_plan["original_plan"] = plan
    return route_plan


def decide_route_from_classification(classification: Dict[str, Any]) -> str:
    """Return top classification category as suggested route."""
    if not classification:
        return "chat"
    return classification.get("category", "chat")


if __name__ == "__main__":
    sample = {"steps": [
        {"step_number": 1, "tool": "read_file", "description": "inspect config"},
        {"step_number": 2, "tool": "write_file", "description": "create file"},
        {"step_number": 3, "tool": "execute_command", "description": "run tests"},
    ]}
    from pprint import pprint
    pprint(route_plan(sample))
