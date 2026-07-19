import re


MAXIMUM_WORDS = 4
METADATA_PREFIX = re.compile(r"^p[0-4](?:-auto)?:", re.IGNORECASE)


def _words(value):
    return re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*", value or "")


def parse_thread_title(title):
    raw = title or ""
    value = raw.strip()
    if not value or "\n" in value or "\r" in value or METADATA_PREFIX.match(value):
        return {"format": "malformed", "reason": "format", "raw": raw}

    word_count = len(_words(value))
    if word_count < 1 or word_count > MAXIMUM_WORDS:
        return {
            "format": "malformed",
            "reason": "word_limit",
            "actualWordCount": word_count,
            "maximumWordCount": MAXIMUM_WORDS,
            "raw": raw,
        }

    return {
        "format": "current",
        "goal": value,
        "wordCount": word_count,
        "raw": raw,
    }
