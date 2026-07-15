import re


CURRENT_TITLE = re.compile(r"^p([0-4])(-auto)?:[ \t]+([^\r\n]+?)[ \t]*$")
REQUIRED_GOAL_WORDS = 4


def _title_words(value):
    return re.findall(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", value or "")


def epic_task_title(priority, epic_id, canonical_title, autonomous=True):
    """Return a stable four-word title that keeps the Epic ID visible."""
    if not re.fullmatch(r"p[0-4]", priority or ""):
        raise ValueError("priority must be p0 through p4")
    if not re.fullmatch(r"[A-Z][A-Z0-9]*-\d{3}", epic_id or ""):
        raise ValueError("epic_id must be a stable uppercase Epic ID")
    words = [word.lower() for word in _title_words(canonical_title) if word.upper() != epic_id]
    words = (words + ["epic", "outcome"])[:2]
    suffix = "-auto" if autonomous else ""
    return f"{priority}{suffix}: implement {epic_id} {' '.join(words)}"


def product_task_title(priority, epic_prefix, autonomous=True):
    """Return the stable title for the product conversation that owns Epic intent."""
    if not re.fullmatch(r"p[0-4]", priority or ""):
        raise ValueError("priority must be p0 through p4")
    prefix_words = _title_words(epic_prefix)
    prefix = (prefix_words[0] if prefix_words else "product").lower()
    suffix = "-auto" if autonomous else ""
    return f"{priority}{suffix}: shape {prefix} product epics"


def parse_thread_title(title):
    current = CURRENT_TITLE.match(title)
    if current:
        goal = current.group(3).strip()
        word_count = len(goal.split())
        if word_count != REQUIRED_GOAL_WORDS:
            return {
                "format": "malformed",
                "reason": "goal_word_count",
                "actualWordCount": word_count,
                "requiredWordCount": REQUIRED_GOAL_WORDS,
                "raw": title,
            }
        return {
            "format": "current",
            "priority": f"p{current.group(1)}",
            "executionMode": "autonomous" if current.group(2) else "review",
            "goal": goal,
            "raw": title,
        }

    return {"format": "malformed", "reason": "format", "raw": title}
