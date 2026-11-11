#!/usr/bin/env python3
"""Structure gate for the custom Odoo modules under addons/.

Checks the code-structure rules of the root AGENTS.md:

* SIZE    a .py or .xml file longer than 250 lines
* FLAT    a loose .py file directly inside a module's models/ folder
* NAMING  a vague file name (utils.py, helpers.py, misc.py, ...)
* DOCS    a class or function in models/ or controllers/ without a docstring
* XMLDOC  an XML file in views/, data/ or security/ without a header comment

Existing violations are frozen in structure_baseline.json. The gate fails only on a
violation that is not in the baseline, or on a SIZE violation that grew.
Run with --update-baseline to freeze the current state (do this only to shrink it).
"""
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADDONS = ROOT / "addons"
BASELINE_FILE = Path(__file__).with_name("structure_baseline.json")
MAX_LINES = 250
TARGET_LINES = 200
VAGUE_STEMS = {"utils", "util", "helpers", "helper", "misc", "common", "tmp", "temp", "new", "old", "stuff"}
VAGUE_PATTERN = re.compile(r"^(test|tmp|temp)\d+$")
XML_FOLDERS = {"views", "data", "security"}
DOC_FOLDERS = {"models", "controllers"}


def rel(path):
    """Return the repo-relative POSIX path used as the key in reports and baseline."""
    return path.relative_to(ROOT).as_posix()


def module_files(suffix):
    """List every file with the given suffix under addons/, skipping caches."""
    return sorted(p for p in ADDONS.rglob("*" + suffix) if "__pycache__" not in p.parts)


def check_size():
    """Map each oversize file to its line count."""
    sizes = {}
    for path in module_files(".py") + module_files(".xml"):
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > MAX_LINES:
            sizes[rel(path)] = lines
    return sizes


def check_flat_models():
    """List loose .py files sitting directly in a models/ folder."""
    return sorted(
        rel(p) for p in module_files(".py")
        if p.parent.name == "models" and p.parent.parent.parent == ADDONS and p.name != "__init__.py"
    )


def check_naming():
    """List files whose name says nothing about their content."""
    return sorted(
        rel(p) for p in module_files(".py") + module_files(".xml")
        if p.stem in VAGUE_STEMS or VAGUE_PATTERN.match(p.stem)
    )


def check_docstrings():
    """List classes and functions in models/ and controllers/ that lack a docstring."""
    missing = []
    for path in module_files(".py"):
        parts = path.relative_to(ADDONS).parts
        if len(parts) < 3 or parts[1] not in DOC_FOLDERS or path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            is_def = isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            if is_def and not node.name.startswith("__") and ast.get_docstring(node) is None:
                missing.append("%s|%s" % (rel(path), node.name))
    return sorted(missing)


def check_xml_headers():
    """List XML files whose first content after <odoo> is not a comment."""
    missing = []
    for path in module_files(".xml"):
        parts = path.relative_to(ADDONS).parts
        if len(parts) < 3 or parts[1] not in XML_FOLDERS:
            continue
        text = path.read_text(encoding="utf-8")
        if not re.search(r"<odoo[^>]*>\s*<!--", text):
            missing.append(rel(path))
    return sorted(missing)


def collect():
    """Run every check and return the violations by rule."""
    return {
        "SIZE": check_size(),
        "FLAT": check_flat_models(),
        "NAMING": check_naming(),
        "DOCS": check_docstrings(),
        "XMLDOC": check_xml_headers(),
    }


def new_violations(current, baseline):
    """Return the violations that are not covered by the baseline."""
    found = []
    for path, lines in current["SIZE"].items():
        if lines > baseline["SIZE"].get(path, 0):
            found.append("SIZE    %s has %d lines (limit %d)" % (path, lines, MAX_LINES))
    for rule in ("FLAT", "NAMING", "DOCS", "XMLDOC"):
        for item in current[rule]:
            if item not in baseline[rule]:
                found.append("%-7s %s" % (rule, item))
    return found


def near_target():
    """Warn about files between the 200-line target and the 250-line cap."""
    warn = []
    for path in module_files(".py") + module_files(".xml"):
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if TARGET_LINES < lines <= MAX_LINES:
            warn.append("%s (%d lines)" % (rel(path), lines))
    return warn


def main(argv):
    """Entry point: print violations and return the process exit code."""
    current = collect()
    if "--update-baseline" in argv:
        BASELINE_FILE.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("Baseline written: %s" % rel(BASELINE_FILE))
        return 0
    empty = {"SIZE": {}, "FLAT": [], "NAMING": [], "DOCS": [], "XMLDOC": []}
    baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8")) if BASELINE_FILE.exists() else empty
    for warning in near_target():
        print("WARNING over the %d-line target: %s" % (TARGET_LINES, warning))
    problems = new_violations(current, baseline)
    for problem in problems:
        print("ERROR   " + problem)
    frozen = sum(len(v) for v in baseline.values())
    print("Structure gate: %d new violation(s), %d frozen in the baseline." % (len(problems), frozen))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
