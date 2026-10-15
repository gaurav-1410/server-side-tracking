"""
Redacts secrets from a Google Tag Manager container export before it is committed.

Replaces the value of any parameter whose key looks like a credential
(token, secret, password, api key, test event code) with "REDACTED".

Usage:
    python scripts/redact_gtm_export.py gtm/server-container.raw.json gtm/server-container-export.json
    python scripts/redact_gtm_export.py gtm/web-container.raw.json    gtm/web-container-export.json

The *.raw.json input files are git-ignored; only the redacted output is committed.
"""
import json
import re
import sys

SENSITIVE_KEY = re.compile(r"(token|secret|password|api[_-]?key|test[_-]?event[_-]?code)", re.IGNORECASE)


def redact(node, found):
    """Walk the export. GTM stores settings as {"type": ..., "key": ..., "value": ...} objects."""
    if isinstance(node, dict):
        key = node.get("key")
        if isinstance(key, str) and SENSITIVE_KEY.search(key) and isinstance(node.get("value"), str) and node["value"]:
            found.append(key)
            node["value"] = "REDACTED"
        for child in node.values():
            redact(child, found)
    elif isinstance(node, list):
        for child in node:
            redact(child, found)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    source, target = sys.argv[1], sys.argv[2]
    if source == target:
        print("Write to a different file than the raw export.", file=sys.stderr)
        return 2
    with open(source, encoding="utf-8") as fh:
        data = json.load(fh)
    found = []
    redact(data, found)
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"Redacted {len(found)} value(s): {sorted(set(found))} -> {target}")
    print("Always open the output and search for your token/secret before committing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
