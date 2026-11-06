"""Build a development artifact from a clean, committed source tree."""

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    if dirty:
        raise SystemExit("Commit the reviewed source before packaging")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    output = destination / f"radiant-climate-{commit[:12]}.zip"
    files = [
        ROOT / "LICENSE",
        ROOT / "README.md",
        ROOT / "SECURITY.md",
        *sorted((ROOT / "docs").glob("*.md")),
        *sorted((ROOT / "custom_components/radiant_climate").rglob("*")),
    ]
    version = json.loads(
        (ROOT / "custom_components/radiant_climate/manifest.json").read_text(encoding="utf-8")
    )["version"]
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(ROOT))
        archive.writestr(
            "BUILD.json",
            json.dumps(
                {
                    "commit": commit,
                    "version": version,
                    "stage": "prerelease" if "-" in version else "release",
                    "approved_for_production": False,
                }
            ),
        )
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".sha256").write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(f"Created {output.name}; SHA-256 {digest}")


if __name__ == "__main__":
    main()
