from typing import Dict, Any
from long_term_memory import LongTermMemory


def handle_segment(segment: Dict[str, Any], session_context: Dict[str, Any], executor=None) -> Dict[str, Any]:
    """Handle knowledge segment by returning retrieved context snippets.

    If `executor` is provided it will not be used here. This is a read-only skeleton.
    """
    ltm = LongTermMemory()
    query = session_context.get("user_prompt", "")
    context = ltm.get_context_for_prompt(query)
    return {"route": "knowledge", "context": context}
