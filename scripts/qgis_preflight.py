"""Preflight checks for the exact QGIS plugin distribution ZIP.

This is an approximation of the public QGIS repository checks, not an approval.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import zipfile
from pathlib import Path

PREFIX = "qgis_dev_probe/"
REQUIRED = {"__init__.py", "metadata.txt", "LICENSE", "plugin.py"}
FORBIDDEN = (".pyc", ".pyo", ".pem", ".key", ".p12", ".pfx")
ENUMS = {
    "Qt": {
        "RichText": "TextFormat", "AlignTop": "AlignmentFlag",
        "AlignLeft": "AlignmentFlag", "TextSelectableByMouse": "TextInteractionFlag",
    },
    "QFrame": {"StyledPanel": "Shape"},
    "Qgis": {"Info": "MessageLevel", "Warning": "MessageLevel",
             "Critical": "MessageLevel", "Success": "MessageLevel"},
    "QgsProcessingParameterDefinition": {"FlagOptional": "Flag"},
}


def check_zip(path: Path) -> list[str]:
    errors = []
    with zipfile.ZipFile(path) as zf:
        infos = zf.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            errors.append("Duplicate ZIP members")
        if any(not name.startswith(PREFIX) or ".." in Path(name).parts for name in names):
            errors.append("Unexpected root or unsafe ZIP path")
        present = {name[len(PREFIX):] for name in names if name.startswith(PREFIX)}
        errors.extend(f"Missing: {name}" for name in sorted(REQUIRED - present))
        for info in infos:
            name = info.filename
            if "__pycache__" in Path(name).parts or name.lower().endswith(FORBIDDEN):
                errors.append(f"Forbidden distribution member: {name}")
            if (info.external_attr >> 16) & 0o002:
                errors.append(f"World-writable ZIP member: {name}")
        if "metadata.txt" in present:
            metadata = zf.read(PREFIX + "metadata.txt").decode("utf-8")
            for key in ("name", "version", "qgisMinimumVersion", "author", "email"):
                if not re.search(r"^" + key + r"=.+$", metadata, re.M):
                    errors.append(f"Missing metadata: {key}")
        for name in sorted(present):
            if not name.endswith(".py"):
                continue
            source = zf.read(PREFIX + name).decode("utf-8")
            try:
                ast.parse(source, filename=name)
            except SyntaxError as exc:
                errors.append(f"Syntax error {name}:{exc.lineno}: {exc.msg}")
            for cls, fields in ENUMS.items():
                for member, scope in fields.items():
                    pattern = r"\b" + cls + r"\." + member + r"\b"
                    for match in re.finditer(pattern, source):
                        line = source.count("\n", 0, match.start()) + 1
                        errors.append(f"Qt6 enum: {name}:{line}: use {cls}.{scope}.{member}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_file", type=Path)
    parser.add_argument("--json-out", type=Path, default=Path("dist/qgis-preflight.json"))
    args = parser.parse_args()
    errors = check_zip(args.zip_file)
    result = {"zip": str(args.zip_file), "status": "FAIL" if errors else "PASS",
              "errors": errors, "note": "Not equivalent to official QGIS approval"}
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
