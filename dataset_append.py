#!/usr/bin/env python3
"""
dataset_append.py

Append a row to a CSV file using arbitrary key=value CLI arguments as columns.

Features:
- Creates the CSV if it doesn't exist.
- Appends rows when columns match.
- Automatically expands the schema when new keys are introduced, rewriting the
  CSV header and backfilling prior rows with empty values for new columns.
- Optional ISO-8601 timestamp column.
- Optionally stamps the filename with a UTC timestamp when creating a new file
  to keep runs separated (e.g., data_20260107T121314Z.csv).

Usage examples:
  python dataset_append.py --file data.csv text="Hello world" label=positive
  python dataset_append.py --file data.csv --add-timestamp text="Hi" model=gpt-4
  python dataset_append.py --file data.csv --stamp-filename-on-create text="Row for a new run"

Notes:
- Pass values with spaces by quoting them.
- Duplicate keys: the last occurrence wins.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Tuple


def parse_pairs(pairs: List[str]) -> Dict[str, str]:
    data: Dict[str, str] = {}
    for raw in pairs:
        if "=" not in raw:
            raise ValueError(f"Invalid pair (expected key=value): {raw}")
        key, value = raw.split("=", 1)
        key = key.strip()
        # Preserve value as-is (CSV stores strings). Strip only trailing newlines.
        value = value.rstrip("\n")
        if not key:
            raise ValueError(f"Empty key in pair: {raw}")
        data[key] = value
    return data


def iso_timestamp() -> str:
    # UTC ISO-8601 with 'Z'
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def filename_timestamp() -> str:
    # Safe for filenames (no ':'), UTC
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def resolve_stamped_path(path: str, enable_stamping: bool) -> Tuple[str, bool]:
    """Return the path to use, stamping the filename if creating a new CSV.

    If stamping is enabled and the target path does not yet exist (or is empty),
    a timestamp suffix is inserted before the extension. If the file exists with
    content, the path is returned unchanged to continue the current dataset.

    Returns (resolved_path, stamped: bool)
    """
    try:
        exists_and_nonempty = os.path.exists(path) and os.path.getsize(path) > 0
    except OSError:
        exists_and_nonempty = False

    if not enable_stamping or exists_and_nonempty:
        return path, False

    directory = os.path.dirname(path)
    base = os.path.basename(path)
    root, ext = os.path.splitext(base)
    if not ext:
        ext = ".csv"
    stamped = f"{root}_{filename_timestamp()}{ext}"
    resolved = os.path.join(directory if directory else "", stamped)
    return resolved, True


def read_existing_csv(path: str) -> Tuple[List[str], List[Dict[str, str]]]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []
        rows = list(reader)
    return list(columns), rows


def write_full_csv(path: str, columns: List[str], rows: List[Dict[str, str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            # Ensure all keys exist
            out = {col: row.get(col, "") for col in columns}
            writer.writerow(out)


def append_row_same_schema(path: str, columns: List[str], row: Dict[str, str]) -> None:
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        out = {col: row.get(col, "") for col in columns}
        writer.writerow(out)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Append a row to a CSV with arbitrary key=value columns.")
    parser.add_argument("pairs", nargs="*", help="Data as key=value pairs (columns=keys)")
    parser.add_argument("--file", "-f", default="dataset.csv", help="Path to CSV file (default: dataset.csv)")
    parser.add_argument(
        "--add-timestamp",
        action="store_true",
        help="Add an ISO-8601 UTC timestamp column to this row.",
    )
    parser.add_argument(
        "--timestamp-col",
        default="timestamp",
        help="Name of the timestamp column when --add-timestamp is used (default: timestamp)",
    )
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress confirmation output")
    # Default enable stamping so fresh runs create uniquely named CSVs; allow opt-out
    parser.add_argument(
        "--stamp-filename-on-create",
        dest="stamp_filename_on_create",
        action="store_true",
        default=True,
        help="When creating a new CSV, stamp the filename with a UTC timestamp.",
    )
    parser.add_argument(
        "--no-stamp-filename-on-create",
        dest="stamp_filename_on_create",
        action="store_false",
        help="Disable filename stamping on new CSV creation.",
    )

    args = parser.parse_args(argv)

    try:
        row = parse_pairs(args.pairs)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    if args.add_timestamp:
        row[args.timestamp_col] = iso_timestamp()

    # Resolve the target CSV path, optionally stamping on first creation
    requested_csv_path = args.file
    csv_path, stamped = resolve_stamped_path(requested_csv_path, args.stamp_filename_on_create)

    # Determine target columns
    if os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
        try:
            existing_cols, existing_rows = read_existing_csv(csv_path)
        except Exception as e:
            print(f"Error reading existing CSV: {e}", file=sys.stderr)
            return 3

        # Preserve existing order; append any new columns in order of appearance
        new_cols = [k for k in row.keys() if k not in existing_cols]
        if new_cols:
            all_cols = existing_cols + new_cols
            # Rewrite entire file with expanded schema, then append this new row
            try:
                write_full_csv(csv_path, all_cols, existing_rows)
                append_row_same_schema(csv_path, all_cols, row)
            except Exception as e:
                print(f"Error writing expanded CSV: {e}", file=sys.stderr)
                return 4
            if not args.quiet:
                info = []
                if stamped and csv_path != requested_csv_path:
                    info.append(f"created {os.path.basename(csv_path)} (stamped from {os.path.basename(requested_csv_path)})")
                info.append(f"added new columns: {', '.join(new_cols)}")
                print("Appended row (" + ", ".join(info) + ").")
        else:
            try:
                append_row_same_schema(csv_path, existing_cols, row)
            except Exception as e:
                print(f"Error appending row: {e}", file=sys.stderr)
                return 5
            if not args.quiet:
                if stamped and csv_path != requested_csv_path:
                    print(f"Appended row (created {os.path.basename(csv_path)}).")
                else:
                    print("Appended row.")
    else:
        # New file: columns are provided keys, in order of appearance
        columns = list(row.keys())
        try:
            write_full_csv(csv_path, columns, [])
            append_row_same_schema(csv_path, columns, row)
        except Exception as e:
            print(f"Error creating new CSV: {e}", file=sys.stderr)
            return 6
        if not args.quiet:
            if csv_path != requested_csv_path and stamped:
                print(f"Created {os.path.basename(csv_path)} (stamped from {os.path.basename(requested_csv_path)}) and appended first row.")
            else:
                print(f"Created {csv_path} and appended first row.")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
