#!/usr/bin/env python3
"""
dataset_guard.py
Checks if a proposed row is a near-duplicate of existing data in the CSV.

Adds token-level normalization and an optional token Jaccard similarity check
to better catch paraphrases and near-duplicates.

Usage:
  python dataset_guard.py --file data.csv --check-col text text="My argument" ...

Returns:
  Exit Code 0: Data is unique (safe to write).
  Exit Code 1: Data is a duplicate (do not write) or invalid input.
"""

import argparse
import csv
import sys
import os
import difflib
import re
import unicodedata


def parse_pairs(pairs):
    data = {}
    for raw in pairs:
        if "=" in raw:
            key, value = raw.split("=", 1)
            data[key.strip()] = value.strip()
    return data


def normalize_text(text: str) -> str:
    # Unicode normalize and lowercase
    s = unicodedata.normalize("NFKC", text or "")
    s = s.lower()
    # Replace URLs and emails
    s = re.sub(r"https?://\S+", " url ", s)
    s = re.sub(r"\b[\w\.-]+@[\w\.-]+\.[a-z]{2,}\b", " email ", s)
    # Replace numbers with a placeholder
    s = re.sub(r"\d+", " 0 ", s)
    # Remove punctuation (keep word characters and whitespace)
    s = re.sub(r"[^\w\s]", " ", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def tokenize(text: str):
    return re.findall(r"\w+", text)


def jaccard_similarity(tokens_a, tokens_b) -> float:
    set_a, set_b = set(tokens_a), set(tokens_b)
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union else 0.0


def difflib_similarity(a: str, b: str) -> float:
    # Returns a float 0.0 to 1.0 (1.0 is identical)
    return difflib.SequenceMatcher(None, a, b).ratio()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Guard against near-duplicate rows by fuzzy-matching a column.")
    parser.add_argument("pairs", nargs="*", help="Data pairs key=value")
    parser.add_argument("--file", "-f", required=True, help="CSV file path")
    parser.add_argument("--check-col", required=True, help="The column name to check for uniqueness")
    parser.add_argument("--threshold", type=float, default=0.78, help="Character-level similarity threshold (0.0-1.0). Default 0.78")
    parser.add_argument("--token-threshold", type=float, default=0.60, help="Token Jaccard threshold (0.0-1.0). Default 0.60")
    parser.add_argument("--no-normalize", action="store_true", help="Disable token/URL/number normalization before comparison")
    parser.add_argument("--min-length", type=int, default=0, help="Minimum normalized length to enforce checks (0 to disable)")

    args = parser.parse_args(argv)
    new_data = parse_pairs(args.pairs)

    # If the file doesn't exist, it's unique by definition
    if not os.path.exists(args.file):
        print("File does not exist yet. Input is unique.")
        return 0

    target_content = new_data.get(args.check_col)
    if not target_content:
        print(f"Error: Proposed data is missing the column '{args.check_col}'.")
        return 1

    try:
        with open(args.file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # If column doesn't exist in CSV yet, we can't check duplicates
            if args.check_col not in (reader.fieldnames or []):
                print("PASS: Column not present yet; treating as unique.")
                return 0

            # Pre-normalize proposed text
            if args.no_normalize:
                norm_new = target_content
            else:
                norm_new = normalize_text(target_content)
            tokens_new = tokenize(norm_new)

            if args.min_length and len(norm_new) < args.min_length:
                print("PASS: Below min-length; skipping duplicate enforcement.")
                return 0

            for i, row in enumerate(reader):
                existing_val = (row.get(args.check_col, "") or "")
                if args.no_normalize:
                    norm_old = existing_val
                else:
                    norm_old = normalize_text(existing_val)
                tokens_old = tokenize(norm_old)

                sim_char = difflib_similarity(norm_new, norm_old)
                sim_tok = jaccard_similarity(tokens_new, tokens_old)

                if sim_char > args.threshold or sim_tok > args.token_threshold:
                    print(
                        "REJECTED: Similar to existing row",
                    )
                    print(f"Row: {i+2}")
                    print(f"Char-sim: {sim_char:.2f} (threshold {args.threshold:.2f})")
                    print(f"Token-Jaccard: {sim_tok:.2f} (threshold {args.token_threshold:.2f})")
                    print(f"Existing: {existing_val}")
                    print(f"Proposed: {target_content}")
                    print("Instruction: Generate a significantly different example.")
                    return 1
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return 1

    print("PASS: Input appears unique.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
