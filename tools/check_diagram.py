#!/usr/bin/env python3
"""Check an Excalidraw scene for the defects a generated diagram should not have.

    python tools/check_diagram.py docs/architecture/system-context.excalidraw

Three things are checked. Every element has the fields Excalidraw needs, so the
file opens rather than erroring. Ids are unique and every bound label points at
a box that exists, so nothing is orphaned. And no free-standing label overlaps
a box it is not inside, which is the defect that makes a diagram look careless
and is the whole reason this scene is generated from coordinates.

Exits non-zero on any failure, so it can be wired into CI later.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED = {
    "id", "type", "x", "y", "width", "height", "angle", "strokeColor",
    "backgroundColor", "fillStyle", "strokeWidth", "strokeStyle", "roughness",
    "opacity", "groupIds", "frameId", "roundness", "seed", "version",
    "versionNonce", "isDeleted", "boundElements", "updated", "link", "locked",
}

problems: list[str] = []


def rect(e: dict) -> tuple[float, float, float, float]:
    return e["x"], e["y"], e["x"] + e["width"], e["y"] + e["height"]


def overlaps(a: dict, b: dict) -> bool:
    ax0, ay0, ax1, ay1 = rect(a)
    bx0, by0, bx1, by1 = rect(b)
    return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1


def inside(a: dict, b: dict) -> bool:
    ax0, ay0, ax1, ay1 = rect(a)
    bx0, by0, bx1, by1 = rect(b)
    return ax0 >= bx0 and ax1 <= bx1 and ay0 >= by0 and ay1 <= by1


def name(e: dict) -> str:
    return (e.get("text") or "").split("\n")[0][:34] or f"<{e['type']}>"


def main(path: Path) -> int:
    scene = json.loads(path.read_text(encoding="utf-8"))
    els = [e for e in scene["elements"] if not e.get("isDeleted")]

    # 1. every element is complete, and nothing is malformed
    for e in els:
        missing = REQUIRED - set(e)
        if missing:
            problems.append(f"{name(e)}: missing {sorted(missing)}")
        if e["width"] < 0 or e["height"] < 0:
            problems.append(f"{name(e)}: negative size")

    # 2. ids are unique and bindings resolve
    ids = [e["id"] for e in els]
    for dupe in {i for i in ids if ids.count(i) > 1}:
        problems.append(f"duplicate id {dupe}")
    known = set(ids)
    for e in els:
        parent = e.get("containerId")
        if parent and parent not in known:
            problems.append(f"{name(e)}: containerId points at nothing")
        for bound in e.get("boundElements") or []:
            if bound["id"] not in known:
                problems.append(f"{name(e)}: boundElements points at nothing")

    # 3. no label lies across a border
    boxes = [e for e in els if e["type"] == "rectangle"]
    free = [e for e in els if e["type"] == "text" and not e.get("containerId")]
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            if overlaps(a, b):
                problems.append(f"boxes overlap: {name(a)} / {name(b)}")
    for label in free:
        for b in boxes:
            if overlaps(label, b) and not inside(label, b):
                problems.append(
                    f"label {name(label)!r} lies across a box border "
                    f"at {rect(label)} vs {rect(b)}"
                )
    for i, a in enumerate(free):
        for b in free[i + 1:]:
            if overlaps(a, b):
                problems.append(f"labels overlap: {name(a)!r} / {name(b)!r}")

    xs = [e["x"] for e in els] + [e["x"] + e["width"] for e in els]
    ys = [e["y"] for e in els] + [e["y"] + e["height"] for e in els]
    print(f"{path}")
    print(f"  elements {len(els)}, boxes {len(boxes)}, "
          f"arrows {sum(1 for e in els if e['type'] == 'arrow')}, "
          f"free labels {len(free)}")
    print(f"  extent   x {min(xs):.0f}..{max(xs):.0f}  y {min(ys):.0f}..{max(ys):.0f}")

    if problems:
        print(f"  FAILED, {len(problems)} problem(s):")
        for p in problems:
            print(f"    {p}")
        return 1
    print("  OK")
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1
                  else "docs/architecture/system-context.excalidraw")
    sys.exit(main(target))
