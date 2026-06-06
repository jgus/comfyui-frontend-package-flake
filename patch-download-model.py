#!/usr/bin/env python3
"""Patch ComfyUI frontend's missingModelDownload bundle to call window.__wmi.start().

Invoked from comfyui-frontend-package's postPatch with no arguments. Runs in the
sdist's unpacked source root. Idempotent and tolerant: only fails on genuinely
catastrophic IO errors. Soft failures (no match, signature missing, already
patched) log and exit 0 so the frontend build still succeeds.
"""

import glob
import os
import re
import sys

BUNDLE_GLOB = "comfyui_frontend_package/static/assets/missingModelDownload-*.js"
MARKER = "/*WMI_PATCHED*/"
SIG_RE = re.compile(r"function downloadModel\((\w+),(\w+)\)\{")


def log(msg):
    print(f"[WMI] {msg}", file=sys.stderr)


def find_function_end(src, start):
    """Brace-counting scanner. `start` points just past the opening `{`.

    Handles nested braces, single/double/backtick strings, and escape sequences.
    Returns the index of the matching `}` or -1 if not found.
    """
    depth = 1
    i = start
    in_str = None
    escape = False
    n = len(src)
    while i < n and depth > 0:
        ch = src[i]
        if in_str is not None:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_str:
                in_str = None
        else:
            if ch in ("'", '"', "`"):
                in_str = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def build_replacement(param_model, param_other):
    t = param_model
    return (
        f"{MARKER}function downloadModel({t},{param_other}){{"
        f"try{{if(window.__wmi&&window.__wmi.start){{window.__wmi.start({t});return;}}}}"
        f"catch(e){{console.error('[WMI] handler error',e);}}"
        f"try{{"
        f"fetch('/api/wmi/download',{{"
        f"method:'POST',"
        f"headers:{{'Content-Type':'application/json'}},"
        f"body:JSON.stringify({{url:{t}.url,filename:{t}.name,directory:{t}.directory}})"
        f"}})"
        f".then(function(r){{return r.json()}})"
        f".then(function(d){{console.log('[WMI] queued',d)}})"
        f".catch(function(e){{console.error('[WMI] fetch error',e);}});"
        f"}}catch(e){{console.error('[WMI] exception',e);}}"
        f"}}"
    )


def pick_bundle(matches):
    if len(matches) == 1:
        return matches[0]
    log(f"multiple bundles matched ({len(matches)}); picking one containing downloadModel(")
    for m in matches:
        try:
            with open(m, "r", encoding="utf-8") as f:
                if "function downloadModel(" in f.read():
                    return m
        except OSError as e:
            log(f"could not read {m}: {e}")
    return matches[0]


def main():
    matches = sorted(glob.glob(BUNDLE_GLOB))
    if not matches:
        log(f"no bundle matched {BUNDLE_GLOB}; skipping")
        return 0

    path = pick_bundle(matches)
    basename = os.path.basename(path)

    with open(path, "r", encoding="utf-8") as f:
        src = f.read()

    if MARKER in src:
        log(f"already patched {basename}")
        return 0

    m = SIG_RE.search(src)
    if not m:
        log("downloadModel signature not found; skipping")
        return 0

    body_start = m.end()
    end_idx = find_function_end(src, body_start)
    if end_idx < 0:
        log("could not find matching `}` for downloadModel; skipping")
        return 0

    replacement = build_replacement(m.group(1), m.group(2))
    patched = src[: m.start()] + replacement + src[end_idx + 1 :]

    with open(path, "w", encoding="utf-8") as f:
        f.write(patched)

    log(f"patched {basename}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

