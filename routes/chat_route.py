from typing import Dict, Any
from smartThinking import SmartThinking


def handle_segment(segment: Dict[str, Any], session_context: Dict[str, Any], executor=None) -> Dict[str, Any]:
    """Handle a chat segment. For Phase 2 this returns a planned reply object.

    If `executor` is provided, it will be ignored for chat segments.
    """
    user_prompt = session_context.get("user_prompt")
    smart = SmartThinking()
    try:
        reply = smart.quick_reply(f"{user_prompt}")
    except Exception:
        reply = "لا توجد خطوات للتنفيذ."
    return {"route": "chat", "reply": reply}
