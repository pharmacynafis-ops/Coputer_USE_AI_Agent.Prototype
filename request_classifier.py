from typing import List, Dict, Any
import re


class RequestClassifier:
    """A lightweight heuristic-first request classifier.

    classify(prompt, conversation_history) -> {category, confidence, candidates}
    Categories: chat, knowledge, analysis, development, automation, security, debug, research
    """

    CATEGORY_KEYWORDS = {
        "development": [r"create file", r"write file", r"implement", r"add feature", r"unit test", r"test file", r"refactor", r"code"],
        "automation": [r"run", r"execute", r"install", r"start service", r"cron", r"schedule", r"command", r"shell"],
        "security": [r"vulnerab", r"password", r"secret", r"credential", r"secure", r"attack", r"exploit"],
        "debug": [r"error", r"exception", r"stacktrace", r"bug", r"traceback", r"fail(ed)?", r"crash"],
        "research": [r"research", r"literature", r"paper", r"cite", r"citation", r"sources", r"study"],
        "knowledge": [r"what is", r"explain", r"how to", r"why", r"where", r"who is", r"define", r"meaning of"],
        "analysis": [r"analyz", r"root cause", r"investigat", r"verify", r"audit", r"assess"],
        "chat": [r"hello", r"hi", r"hey", r"thanks", r"thank you", r"good morning", r"good evening"]
    }

    def __init__(self):
        # Precompile regexes
        self._patterns = {c: [re.compile(p, re.I) for p in pats] for c, pats in self.CATEGORY_KEYWORDS.items()}

    def classify(self, prompt: str, conversation_history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        prompt_text = (prompt or "").lower()
        scores = {c: 0.0 for c in self._patterns.keys()}

        # Simple keyword scoring
        for cat, patterns in self._patterns.items():
            for pat in patterns:
                if pat.search(prompt_text):
                    scores[cat] += 1.0

        # Normalize to confidence in 0..1
        max_score = max(scores.values()) if scores else 0.0
        candidates = []
        for cat, sc in scores.items():
            if max_score > 0:
                conf = round(sc / max_score, 2)
            else:
                conf = 0.0
            candidates.append({"category": cat, "confidence": conf})

        # Sort candidates by confidence desc
        candidates.sort(key=lambda x: x["confidence"], reverse=True)

        top = candidates[0] if candidates else {"category": "chat", "confidence": 0.0}

        # Heuristic adjustments: if top is very low, prefer chat with low confidence
        if top["confidence"] < 0.25:
            result = {"category": "chat", "confidence": 0.5, "candidates": candidates}
        else:
            result = {"category": top["category"], "confidence": top["confidence"], "candidates": candidates}

        return result


if __name__ == "__main__":
    rc = RequestClassifier()
    tests = [
        "Create a new file that implements a login handler",
        "How do I secure passwords in the database?",
        "There is an exception in server.py with a traceback",
        "Search for references to 'authentication' in project files",
        "Hi, how are you?",
    ]
    for t in tests:
        print(t, "->", rc.classify(t))
