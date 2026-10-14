#!/usr/bin/env python3
"""
Pack the clinical analysis package into one JSON file for the browser.

The hosted demo runs the exact same Python the local service runs, inside
Pyodide, so the package is shipped as text and written into the interpreter's
in-memory file system at start-up.

Usage: build-nlp-bundle.py <output.json>
"""
import hashlib
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "asr")
PACKAGE = "nlp"
# Nothing else leaves the machine: no tests, no service code, no caches.
ALLOWED_SUFFIXES = (".py", ".json")


def collect():
    files = {}
    base = os.path.join(ROOT, PACKAGE)
    for directory, subdirs, names in os.walk(base):
        subdirs[:] = sorted(d for d in subdirs if d != "__pycache__")
        for name in sorted(names):
            if not name.endswith(ALLOWED_SUFFIXES):
                continue
            path = os.path.join(directory, name)
            key = os.path.relpath(path, ROOT).replace(os.sep, "/")
            with open(path, "r", encoding="utf-8") as handle:
                files[key] = handle.read()
    return files


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    files = collect()
    if "nlp/pipeline.py" not in files or "nlp/data/medications.json" not in files:
        sys.exit("bundle is missing core files: " + ", ".join(sorted(files)))

    digest = hashlib.sha256(
        json.dumps(files, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    out = sys.argv[1]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as handle:
        json.dump({"version": digest, "files": files}, handle, ensure_ascii=False,
                  separators=(",", ":"))
    print("nlp bundle: {0} files, {1} KB, version {2}".format(
        len(files), os.path.getsize(out) // 1024, digest))


if __name__ == "__main__":
    main()
