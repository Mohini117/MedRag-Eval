import re


ABSTAIN_ANSWER = "I cannot answer this based on the available information."

_NON_ALNUM_RE = re.compile(r"[^a-z]+")


def normalize_binary_label(value: str | None) -> str | None:
    if not value:
        return None
    normalized = _NON_ALNUM_RE.sub("", value.lower())
    if normalized in {"yes", "no", "maybe", "unknown"}:
        return normalized
    return None


def extract_binary_verdict(answer: str | None) -> str | None:
    if not answer:
        return None

    normalized_answer = answer.strip().lower()
    if ABSTAIN_ANSWER.lower() in normalized_answer:
        return "abstain"

    first_line = normalized_answer.splitlines()[0].strip()
    first_sentence = re.split(r"[.!?]", first_line, maxsplit=1)[0].strip()

    for label in ("yes", "no", "maybe"):
        if re.match(rf"^{label}\b", first_sentence):
            return label

    return None


def evaluate_binary_answer(
    answer: str | None,
    expected_label: str | None,
) -> dict:
    expected_verdict = normalize_binary_label(expected_label)
    predicted_verdict = extract_binary_verdict(answer)

    is_correct = None
    if expected_verdict is not None:
        is_correct = predicted_verdict == expected_verdict

    return {
        "expected_verdict": expected_verdict,
        "predicted_verdict": predicted_verdict,
        "is_correct": is_correct,
        "is_abstained": predicted_verdict == "abstain",
    }
