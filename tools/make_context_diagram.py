#!/usr/bin/env python3
"""Generate the system context diagram as an Excalidraw scene.

    python tools/make_context_diagram.py
    # then open docs/architecture/system-context.excalidraw at excalidraw.com
    # and export an SVG next to it, with "Embed scene" ticked

Why a script and not a drawing. A diagram drawn by hand is a binary nobody can
review: a reader cannot tell what changed between two versions, and whoever
drew it is the only person who can correct it. Here the layout is code, so a
wrong figure is a one-line diff and the scene can be regenerated. The output is
still a real Excalidraw file, so anyone can open it and nudge things.

Why Excalidraw rather than Mermaid. Mermaid places the boxes for you, which is
fine until the arrangement is the thing you are trying to control. This diagram
needs the system in the middle, people on the left, the one external service
top right, and nothing crossing. Excalidraw also matches
`context-diagram.svg`, which the team already drew that way.

What the diagram follows, from the C4 guidance: every diagram carries a key,
and a title naming its type and scope. Colour means something and is stated in
the key; the diagram still reads in black and white because the key repeats
every distinction in words, and the one thing that is not built is dashed as
well as labelled.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

OUT = Path("docs/architecture/system-context.excalidraw")

# Excalidraw constants, from packages/common/src/constants.ts
FONT_HAND = 5          # FONT_FAMILY.Excalifont
ADAPTIVE_RADIUS = 3    # ROUNDNESS.ADAPTIVE_RADIUS

# One colour per kind of thing, and the key says so in words as well.
PERSON = ("#2f9e44", "#b2f2bb")      # stroke, fill
SYSTEM = ("#6741d9", "#e0dbfc")
EXTERNAL = ("#343a40", "#e9ecef")
STORE = ("#e8590c", "#ffec99")
QUIET = ("#868e96", "transparent")
INK = "#1e1e1e"

# Excalifont is a touch narrower than the box-drawing estimate suggests.
CHAR_W = 0.53
LINE_H = 1.25

rng = random.Random(20261104)       # stable ids and seeds, so reruns diff cleanly
elements: list[dict[str, Any]] = []


def _seed() -> int:
    return rng.randint(1, 2_000_000_000)


def _id() -> str:
    return "".join(rng.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(20))


def _base(kind: str, x: float, y: float, w: float, h: float, **over: Any) -> dict[str, Any]:
    element = {
        "id": _id(), "type": kind, "x": x, "y": y, "width": w, "height": h,
        "angle": 0, "strokeColor": INK, "backgroundColor": "transparent",
        "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid",
        "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None,
        "index": None, "roundness": None, "seed": _seed(), "version": 1,
        "versionNonce": _seed(), "isDeleted": False, "boundElements": None,
        "updated": 1, "link": None, "locked": False,
    }
    element.update(over)
    return element


def text(body: str, x: float, y: float, size: int = 16, colour: str = INK,
         align: str = "left", width: float | None = None) -> dict[str, Any]:
    """A free-standing label. Width is estimated from the font metrics."""
    lines = body.split("\n")
    w = width if width is not None else max(len(line) for line in lines) * size * CHAR_W
    h = len(lines) * size * LINE_H
    element = _base(
        "text", x, y, w, h,
        strokeColor=colour, fontSize=size, fontFamily=FONT_HAND,
        text=body, originalText=body, textAlign=align, verticalAlign="top",
        containerId=None, lineHeight=LINE_H, autoResize=True, baseFontSize=None,
    )
    elements.append(element)
    return element


def box(label: str, x: float, y: float, w: float, h: float,
        colour: tuple[str, str], size: int = 16, dashed: bool = False,
        weight: int = 1) -> dict[str, Any]:
    """A labelled box. The label is bound to it, so moving one moves both."""
    stroke, fill = colour
    rect = _base(
        "rectangle", x, y, w, h,
        strokeColor=stroke, backgroundColor=fill, fillStyle="solid",
        strokeWidth=weight, strokeStyle="dashed" if dashed else "solid",
        roundness={"type": ADAPTIVE_RADIUS},
    )
    lines = label.split("\n")
    th = len(lines) * size * LINE_H
    tw = max(len(line) for line in lines) * size * CHAR_W
    inner = _base(
        "text", x + (w - tw) / 2, y + (h - th) / 2, tw, th,
        strokeColor=INK, fontSize=size, fontFamily=FONT_HAND,
        text=label, originalText=label, textAlign="center", verticalAlign="middle",
        containerId=rect["id"], lineHeight=LINE_H, autoResize=True, baseFontSize=None,
    )
    rect["boundElements"] = [{"id": inner["id"], "type": "text"}]
    elements.extend([rect, inner])
    return rect


def arrow(start: tuple[float, float], end: tuple[float, float],
          dashed: bool = False, colour: str = INK) -> dict[str, Any]:
    """A straight arrow between two points. Unbound, so nothing re-routes it."""
    x0, y0 = start
    x1, y1 = end
    element = _base(
        "arrow", x0, y0, abs(x1 - x0), abs(y1 - y0),
        strokeColor=colour, strokeWidth=1,
        strokeStyle="dashed" if dashed else "solid",
        points=[[0, 0], [x1 - x0, y1 - y0]],
        startBinding=None, endBinding=None,
        startArrowhead=None, endArrowhead="arrow", elbowed=False,
        roundness={"type": 2},
    )
    elements.append(element)
    return element


# ----------------------------------------------------------------- layout
#
# One row for the main flow, the external service above it and the data store
# below, so no arrow crosses another. Coordinates are explicit because that is
# the whole reason for not letting a layout engine place them.

text("System context: SME Procurement-Preparation Agent", 60, 40, size=28)
text("Who uses it, what it depends on, and what it refuses to touch.\n"
     "Everything inside the boundary was built by the team. All data is synthetic.",
     60, 82, size=14, colour="#495057")

officer = box("Procurement officer\n\nStarts every review\nand confirms twice",
              60, 250, 230, 130, PERSON)

system = box("Procurement-preparation agent\n\nBounded loop, fixed steps,\nwrites DRAFT and nothing else",
             420, 230, 320, 170, SYSTEM, weight=2)

gemini = box("Gemini API\n\nExternal. Reads quotations,\nfinds the policy clause",
             900, 60, 250, 130, EXTERNAL)

manager = box("Procurement manager\n\nApproval happens\noutside this release",
              900, 265, 250, 130, PERSON, dashed=True)

store = box("Data store\n\nPolicy corpus, stock,\nsuppliers, quotations, traces",
            420, 480, 320, 130, STORE)

never = box("Never connected: no purchase order,\nno supplier contact, no payment",
            860, 480, 330, 90, QUIET, size=14, dashed=True)

# --- arrows, left to right, then up to the model and down to the store
#
# The gaps between the boxes are wide enough for the label that sits in them.
# Every label is checked against every box by tools/check_diagram.py, because a
# label lying across a border is the one defect a hand-drawn diagram always has
# and the only reason to generate this one from coordinates.
arrow((290, 315), (415, 315))
text("starts a review", 298, 285, size=14, colour="#495057")

arrow((745, 275), (895, 150))
text("document text,\npolicy questions", 757, 182, size=14, colour="#495057")

arrow((745, 330), (895, 330), dashed=True)
text("a DRAFT requisition,\nhanded over by hand", 748, 288, size=14, colour="#495057")

arrow((580, 405), (580, 475))
text("reads governed data,\nwrites drafts and traces", 598, 418, size=14, colour="#495057")

arrow((775, 525), (855, 525), dashed=True, colour="#adb5bd")

# ------------------------------------------------------------------- key
#
# C4's one hard rule. It repeats every distinction in words so the diagram
# still works printed in black and white.
box("", 60, 480, 290, 190, ("#adb5bd", "transparent"))
text("KEY", 80, 495, size=16)
text("green      a person who uses it\n"
     "violet     the system we built\n"
     "grey       outside, not ours\n"
     "yellow     data inside the boundary\n"
     "dashed     not built in this release",
     80, 525, size=14, colour="#495057")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({
    "type": "excalidraw",
    "version": 2,
    "source": "tools/make_context_diagram.py",
    "elements": elements,
    "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
    "files": {},
}, indent=2) + "\n", encoding="utf-8")

print(f"wrote {OUT}")
print(f"  elements: {len(elements)}")
print(f"  boxes:    {sum(1 for e in elements if e['type'] == 'rectangle')}")
print(f"  arrows:   {sum(1 for e in elements if e['type'] == 'arrow')}")
print("Open it at excalidraw.com, then export SVG with 'Embed scene' ticked.")
