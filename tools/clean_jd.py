"""JD preprocessing: normalise encoding, fix collapsed words, trim whitespace."""

import re
import unicodedata


def clean_jd(raw: str) -> str:
    """Clean a raw job description string.

    Fixes common artefacts from JobSpy/LinkedIn scraping:
    - Unicode characters normalised to ASCII equivalents
    - Collapsed words fixed: "experienceIn" -> "experience In"
    - Excessive blank lines collapsed to two at most
    - Runs of spaces/tabs collapsed to single space
    - Non-breaking spaces converted to regular space
    """
    text = unicodedata.normalize("NFKC", raw)           # normalise unicode
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)   # fix collapsed words
    text = re.sub(r'\n{3,}', '\n\n', text)              # max 2 consecutive newlines
    text = re.sub(r'[ \t]{2,}', ' ', text)              # collapse runs of spaces
    text = re.sub(r'\xa0', ' ', text)                   # non-breaking spaces
    return text.strip()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        raw = open(sys.argv[1], encoding="utf-8").read()
    else:
        raw = sys.stdin.read()
    print(clean_jd(raw))
