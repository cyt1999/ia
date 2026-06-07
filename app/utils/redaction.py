SENSITIVE_MARKERS = ("key", "secret", "token", "password", "authorization")


def redact_mapping(values: dict) -> dict:
    redacted = {}
    for key, value in values.items():
        if any(marker in key.lower() for marker in SENSITIVE_MARKERS):
            redacted[key] = "[REDACTED]"
        else:
            redacted[key] = value
    return redacted

