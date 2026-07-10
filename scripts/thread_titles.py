import re


CURRENT_TITLE = re.compile(r"^p([0-4])(-auto)?:[ \t]+([^\r\n]+?)[ \t]*$")
REQUIRED_GOAL_WORDS = 4


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
