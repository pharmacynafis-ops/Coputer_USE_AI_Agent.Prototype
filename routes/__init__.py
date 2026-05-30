"""Routes package (Phase 2 skeletons).

Each module exposes a `handle_segment(segment, session_context, executor=None)` function.
These handlers are skeletons and do not perform side-effects unless an `executor`
callable is provided. The `executor` callable should match the signature:
    executor(tool_name: str, arguments: dict) -> str

This package is intentionally non-invasive for Phase 2.
"""

from . import chat_route, knowledge_route, analysis_route, development_route, automation_route, security_route, debug_route, research_route  # noqa
