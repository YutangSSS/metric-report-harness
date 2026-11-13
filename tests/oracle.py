"""An independent recount in plain Python, straight from the CSVs, with no SQL and no harness code.

If the SQL models and this file disagree, one of them has a bug. Agreement on the real data is the evidence
that the numbers are right, not just that the code runs.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def _region(loc: str) -> str:
    if loc == "Outside Jurisdiction":
        return "Outside jurisdiction"
    if loc.endswith("Austin (TX)") and not loc.endswith("Travis (TX)"):
        return "City of Austin"
    return "Rest of Travis County"


def load(data_dir: Path):
    seen, intakes = set(), []
    with (data_dir / "aac_intakes.csv").open() as f:
        for r in csv.DictReader(f):
            key = (r["animal_id"], r["datetime"][:19])
            if key in seen:
                continue
            seen.add(key)
            intakes.append({"animal": r["animal_id"], "t": datetime.fromisoformat(r["datetime"][:19]),
                            "region": _region(r["found_location"]), "type": r["intake_type"], "animal_type": r["animal_type"]})
    outcomes = defaultdict(list)
    with (data_dir / "aac_outcomes.csv").open() as f:
        for r in csv.DictReader(f):
            outcomes[r["animal_id"]].append(datetime.fromisoformat(r["datetime"][:19]))
    by_animal = defaultdict(list)
    for i in intakes:
        by_animal[i["animal"]].append(i)
    stays = []
    for animal, ins in by_animal.items():
        ins.sort(key=lambda i: i["t"])
        outs = sorted(outcomes.get(animal, []))
        for k, i in enumerate(ins):
            nxt = ins[k + 1]["t"] if k + 1 < len(ins) else None
            match = [o for o in outs if o >= i["t"] and (nxt is None or o < nxt)]
            end = match[0] if match else nxt  # closed at the next intake when no outcome was recorded
            stays.append({**i, "end": end})
    return stays


def intakes(stays, start: datetime, end: datetime, region: str | None = None) -> int:
    return sum(1 for s in stays if start <= s["t"] < end and (region is None or s["region"] == region))


def in_care(stays, at: datetime, region: str | None = None) -> int:
    return sum(1 for s in stays if s["t"] < at and (s["end"] is None or s["end"] >= at)
               and (region is None or s["region"] == region))
