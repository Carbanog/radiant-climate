"""Keep the displayed release version consistent without importing HA."""

import ast
import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    component = ROOT / "custom_components/radiant_climate"
    version = json.loads((component / "manifest.json").read_text(encoding="utf-8"))["version"]
    constants = ast.parse((component / "const.py").read_text(encoding="utf-8"))
    declared = next(
        ast.literal_eval(node.value)
        for node in constants.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "VERSION" for target in node.targets)
    )
    package = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    displayed = re.search(r"\*\*Versión: v([^\s]+)\.\*\*", readme)
    assert displayed is not None, "README release version missing"
    assert declared == package == displayed[1] == version, "Release versions disagree"
    print("Manifest, constants, package and README versions agree.")


if __name__ == "__main__":
    main()
