#!/usr/bin/env python3
"""Run the release-gate validation over a drafts file, locally.

Usage:
  python3 validate_drafts.py --source ../sources/book-of-mormon.json \
      --drafts drafts.jsonl [--show 10] [--out-rejects rejects.jsonl]

The API applies exactly these checks on import ({"task":"validate_exercises"}),
so the pass rate here is the pass rate you will get in production — this just
lets you measure a generation run before spending an import on it. Nothing is
written to the database.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))

from app.services.exercise_validation import check_payload


def verses_by_chapter(source: dict) -> dict[str, dict[str, str]]:
    """chapter_ref -> {verse ref_label: text}, mirroring what the DB holds."""
    chapters = {}
    for book in source["books"]:
        for chapter in book["chapters"]:
            ref = chapter.get("reference", f"{book['book']} {chapter['chapter']}")
            chapters[ref] = {v["reference"]: v["text"] for v in chapter["verses"]}
    return chapters


def category(problem: str) -> str:
    """Collapse a problem message to its kind, so counts are readable."""
    if "not in this chapter" in problem:
        return "verse_ref not in this chapter"
    if "appears in the chapter text" in problem:
        return "distractor appears in chapter"
    if "not verbatim scripture" in problem:
        return "display_text not verbatim"
    if "answer phrase does not appear" in problem:
        return "answer not in chapter"
    return problem


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--drafts", required=True)
    parser.add_argument("--show", type=int, default=5, help="Example failures to print")
    parser.add_argument("--out-rejects", default=None, help="Write failing drafts here")
    args = parser.parse_args()

    chapters = verses_by_chapter(json.loads(Path(args.source).read_text()))
    counts = Counter()
    by_kind = Counter()
    failures = []

    for line in Path(args.drafts).read_text().splitlines():
        if not line.strip():
            continue
        draft = json.loads(line)
        verses = chapters.get(draft["chapter_ref"], {})
        problems = check_payload(draft["kind"], draft["payload"], verses)
        by_kind[draft["kind"], bool(problems)] += 1
        if problems:
            failures.append((draft, problems))
            for problem in problems:
                counts[category(problem)] += 1

    total = sum(by_kind.values())
    failed = len(failures)
    if not total:
        sys.exit("No drafts found.")

    print(f"drafts: {total}   passed: {total - failed}   failed: {failed} "
          f"({failed / total:.1%})")
    for kind in sorted({k for k, _ in by_kind}):
        ok, bad = by_kind[kind, False], by_kind[kind, True]
        rate = bad / (ok + bad) if ok + bad else 0
        print(f"  {kind:6s} passed {ok:4d}  failed {bad:4d}  ({rate:.1%})")
    if counts:
        print("\nfailures by cause:")
        for cause, n in counts.most_common():
            print(f"  {n:4d}  {cause}")

    for draft, problems in failures[: args.show]:
        print(f"\n--- {draft['chapter_ref']} ({draft['kind']})")
        for problem in problems:
            print(f"    ! {problem}")
        print(f"    {json.dumps(draft['payload'])[:400]}")

    if args.out_rejects:
        with Path(args.out_rejects).open("w") as out:
            for draft, problems in failures:
                out.write(json.dumps({**draft, "problems": problems}) + "\n")
        print(f"\nwrote {failed} rejects → {args.out_rejects}")


if __name__ == "__main__":
    main()
