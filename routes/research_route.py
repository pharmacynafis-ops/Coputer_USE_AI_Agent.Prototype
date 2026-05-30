from typing import Dict, Any
import os
import time
from long_term_memory import LongTermMemory


def _external_search(query: str, api_key: str) -> Dict[str, Any]:
    """Attempt an external search using a hypothetical connector.

    This implementation is purposely conservative: if no connector is configured
    it returns Evidence Not Found. Connectors can be added later behind an env flag.
    """
    # No external connector implemented in Phase 6. Respect the approved docs.
    return {"found": False, "reason": "connectors_not_configured"}


def handle_segment(segment: Dict[str, Any], session_context: Dict[str, Any], executor=None) -> Dict[str, Any]:
    """Research handler: orchestrate external search or persist research intent.

    Behavior:
    - If an external search API key is configured, attempt a best-effort search via `_external_search`.
    - Otherwise, persist the research request into LongTermMemory and return `Evidence Not Found`.
    """
    query = session_context.get("user_prompt", "")
    api_key = os.getenv("EXTERNAL_SEARCH_API_KEY")
    ltm = LongTermMemory()

    if api_key:
        try:
            results = _external_search(query, api_key)
            if results.get("found"):
                # Persist artifact
                artifact_name = f"research_{session_context.get('session_id','unknown')}_{int(time.time())}"
                ltm.add_research_artifact(artifact_name, results.get('summary', ''), sources=results.get('sources', {}))
                return {"route": "research", "status": "found", "results": results}
            else:
                # Not found by connector
                ltm.add_research_artifact(f"research_pending_{int(time.time())}", f"No evidence found for query: {query}", sources={})
                return {"route": "research", "status": "evidence_not_found", "note": results.get('reason')}
        except Exception as e:
            return {"route": "research", "status": "error", "error": str(e)}

    # No connector configured: persist intent and return Evidence Not Found
    try:
        artifact_name = f"research_intent_{session_context.get('session_id','unknown')}_{int(time.time())}"
        ltm.add_research_artifact(artifact_name, f"Pending research: {query}", sources={})
    except Exception:
        pass

    return {"route": "research", "status": "evidence_not_found", "intended_query": query, "note": "connectors not implemented"}
