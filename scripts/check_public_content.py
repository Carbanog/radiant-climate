"""Check tracked text for obvious secrets and private installation details.

This complements manual review; it is not a comprehensive secret scanner.
Only filenames and rule names are printed if a match is found.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "private_network_address": r"\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})\b",
    "windows_profile_path": r"(?i)[A-Z]:[\\/](?:Users|Documentos)[\\/]",
    "github_credential": r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b",
    "private_key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "credential_assignment": r"""(?i)["']?(?:password|access_token|api_key)["']?\s*[:=]\s*["'][^"']{12,}["']""",
}


def main():
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)
    errors = []
    for name in result.stdout.decode().split("\0"):
        if not name:
            continue
        path = ROOT / name
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append((name, "unexpected_binary_file"))
            continue
        for label, pattern in PATTERNS.items():
            if re.search(pattern, content):
                errors.append((name, label))
    for name, label in errors:
        print(f"{name}: {label}")
    if errors:
        sys.exit(1)
    print("Tracked content passed privacy checks; manual review is still required.")


if __name__ == "__main__":
    main()
