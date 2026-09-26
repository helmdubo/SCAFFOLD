"""
Layer: dev tooling

Rules:
- Host-side wrapper for the Tier 3 headless Blender smoke runner.
- Runs outside Blender; spawns `blender -b` and never imports bpy.
- Token-lean output: one table row per object, or only baseline diffs.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNNER = HERE / "blender_smoke.py"
VOLATILE_FIELDS = frozenset({"ms", "residual_max"})  # machine/numpy dependent
TABLE_COLUMNS = (
    ("object", 30),
    ("faces", 5),
    ("patches", 7),
    ("families", 8),
    ("family_max", 10),
    ("opposite_side_families", 3),
    ("islands", 7),
    ("rigid_islands", 5),
    ("pinned", 6),
    ("oblique_runs", 5),
    ("solve_diagnostics", 4),
    ("residual_max", 8),
    ("ms", 6),
)
COLUMN_TITLES = {
    "opposite_side_families": "opp",
    "rigid_islands": "rigid",
    "oblique_runs": "obliq",
    "solve_diagnostics": "diag",
}


def main() -> int:
    args = _parse_args()
    blender = _find_blender(args.blender)
    out = Path(args.out) if args.out else HERE / "reports" / f"{Path(args.blend).stem}.smoke.json"
    command = [
        blender, "-b", "--factory-startup", args.blend,
        "--python", str(RUNNER), "--",
        "--out", str(out), "--selection", args.selection,
    ]
    if args.objects:
        command += ["--objects", args.objects]
    if args.seamed:
        command.append("--seamed")
    if args.write_uv:
        command.append("--write-uv")
    if args.capture_dir:
        command += ["--capture-dir", args.capture_dir]

    completed = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout)
    records = [
        json.loads(line[len("SMOKE "):])
        for line in completed.stdout.splitlines()
        if line.startswith("SMOKE ")
    ]
    if not records:
        tail = (completed.stdout + completed.stderr).strip().splitlines()[-15:]
        print(f"blender exited {completed.returncode} without SMOKE records:")
        print("\n".join(tail))
        return 2

    errors = [record for record in records if "error" in record]
    if args.baseline:
        exit_code = _compare_with_baseline(records, Path(args.baseline), args.update_baseline)
    else:
        _print_table(records)
        exit_code = 0
    for record in errors:
        print(f"ERROR {record['object']}: {record['error']}")
    print(f"{len(records)} objects, {len(errors)} errors, report {out}")
    return 1 if errors else exit_code


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Scaffold Tier 3 Blender smoke test.")
    parser.add_argument("blend", help="path to the .blend file")
    parser.add_argument("--objects", default="", help="comma-separated object names")
    parser.add_argument("--seamed", action="store_true", help="all mesh objects with UV seams")
    parser.add_argument("--selection", choices=("file", "all"), default="file")
    parser.add_argument("--write-uv", action="store_true", help="also exercise the UV write boundary")
    parser.add_argument("--capture-dir", default="", help="dump SourceMeshSnapshot JSON per object")
    parser.add_argument("--baseline", default="", help="compare stable fields with this JSON baseline")
    parser.add_argument("--update-baseline", action="store_true", help="rewrite --baseline from this run")
    parser.add_argument("--blender", default="", help="Blender executable (else $SCAFFOLD_BLENDER)")
    parser.add_argument("--out", default="", help="full JSON report path")
    parser.add_argument("--timeout", type=int, default=900)
    return parser.parse_args()


def _find_blender(explicit: str) -> str:
    candidates = [explicit, os.environ.get("SCAFFOLD_BLENDER", "")]
    candidates += sorted(glob.glob("/opt/blender/*/blender"), reverse=True)
    candidates += sorted(glob.glob("C:/Program Files/Blender Foundation/Blender */blender.exe"), reverse=True)
    candidates.append(shutil.which("blender") or "")
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    sys.exit("Blender not found: pass --blender or set SCAFFOLD_BLENDER.")


def _stable(record: dict) -> dict:
    return {key: value for key, value in record.items() if key not in VOLATILE_FIELDS}


def _compare_with_baseline(records: list[dict], path: Path, update: bool) -> int:
    current = {record["object"]: _stable(record) for record in records}
    if update or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"baseline written: {path} ({len(current)} objects)")
        return 0
    baseline = json.loads(path.read_text(encoding="utf-8"))
    diffs = []
    for name in sorted(set(baseline) | set(current)):
        old, new = baseline.get(name), current.get(name)
        if old is None or new is None:
            diffs.append(f"{name}: {'added' if old is None else 'missing'}")
            continue
        for key in sorted(set(old) | set(new)):
            if old.get(key) != new.get(key):
                diffs.append(f"{name}.{key}: {old.get(key)!r} -> {new.get(key)!r}")
    if diffs:
        print(f"{len(diffs)} baseline differences:")
        print("\n".join(diffs))
        return 1
    print(f"baseline identical ({len(current)} objects)")
    return 0


def _print_table(records: list[dict]) -> None:
    header = " ".join(
        COLUMN_TITLES.get(key, key)[:width].ljust(width) if key == "object"
        else COLUMN_TITLES.get(key, key)[:width].rjust(width)
        for key, width in TABLE_COLUMNS
    )
    print(header)
    for record in records:
        cells = []
        for key, width in TABLE_COLUMNS:
            value = record.get(key, "-")
            text = str(value)
            cells.append(text[:width].ljust(width) if key == "object" else text[:width].rjust(width))
        print(" ".join(cells))


if __name__ == "__main__":
    raise SystemExit(main())
