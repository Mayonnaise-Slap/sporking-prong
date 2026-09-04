def parse_submission_text(content: bytes) -> str:
    return content.decode("utf-8", errors="replace")
