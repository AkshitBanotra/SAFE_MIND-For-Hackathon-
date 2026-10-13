#!/usr/bin/env python3

import re

assessment = """
FA=85
SH=80
HP=75
IM=75
SD=75
DF=80
SELF=1
DANGER=0
"""

def parse_assessment(raw: str) -> dict[str, int]:

    EXPECTED_KEYS = {
        "FA", "SH", "HP", "IM",
        "SD", "DF", "SELF", "DANGER"
    }

    pattern = r"(?m)^\s*([A-Z]+)\s*=\s*(\d+)\s*$"

    pairs = re.findall(pattern, raw)
    result = {}

    for key, value in pairs:
        if key not in EXPECTED_KEYS:
            continue

        if key in result:
            raise ValueError(f"Duplicate assessment key: {key}")

        result[key] = int(value)

    missing = EXPECTED_KEYS - result.keys()

    if missing:
        raise ValueError(f"Missing assessment keys: {sorted(missing)}")

    return result


print(parse_assessment(assessment))
