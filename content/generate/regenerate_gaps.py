#!/usr/bin/env python3
"""Refill lessons that fell below the target exercise count.

Rejecting or retiring an exercise leaves a hole that nothing refills. This
asks the API which lessons are short, regenerates only those chapters through
the same Batches pipeline, and tells the model which previous attempts were
rejected so it doesn't reproduce them.

Usage:
  python3 regenerate_gaps.py --source ../sources/book-of-mormon.json \
      --work book-of-mormon --target 4 --out refill.jsonl

Then upload refill.jsonl to the data bucket and invoke
{"task": "import_exercises", ...} followed by {"task": "validate_exercises", ...}.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import anthropic

from generate_exercises import MODEL, PROMPTS_DIR, api_key
from schemas import PAYLOAD_SCHEMAS, api_json_schema

LAMBDA = "scripturebuddy-api"
REGION = "us-west-2"


def fetch_gaps(work_slug: str, target: int) -> dict:
    """Ask the deployed API which lessons are short."""
    out = Path("/tmp/sb-gaps.json")
    subprocess.run(
        [
            "aws", "lambda", "invoke",
            "--region", REGION,
            "--function-name", LAMBDA,
            "--cli-binary-format", "raw-in-base64-out",
            "--payload",
            json.dumps({"task": "content_gaps", "work_slug": work_slug, "target": target}),
            "--cli-read-timeout", "300",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    data = json.loads(out.read_text())
    if data.get("status") != "ok":
        sys.exit(f"content_gaps failed: {data}")
    return data


def avoid_block(avoid: list[dict]) -> str:
    """Render rejected attempts as explicit negative examples."""
    if not avoid:
        return ""
    lines = [
        "\nPrevious attempts for this chapter were REJECTED. Do not repeat them, "
        "and do not produce anything that fails for the same reason:",
    ]
    for item in avoid[:6]:
        why = item.get("why") or "rejected by the curator"
        lines.append(f"- {json.dumps(item['payload'], ensure_ascii=False)}\n  Rejected because: {why}")
    return "\n".join(lines) + "\n"


def build_requests(source: dict, gaps: list[dict]) -> tuple[list[dict], dict]:
    chapters = {
        (book["lds_slug"], chapter["chapter"]): (book, chapter)
        for book in source["books"]
        for chapter in book["chapters"]
    }
    requests, meta = [], {}
    for gap in gaps:
        kind = gap["exercise_kind"]
        if kind not in PAYLOAD_SCHEMAS:
            continue
        found = chapters.get((gap["book_slug"], gap["chapter"]))
        if found is None:
            print(f"  no source chapter for {gap['lesson_title']}", file=sys.stderr)
            continue
        book, chapter = found
        chapter_ref = chapter.get("reference", f"{book['book']} {chapter['chapter']}")
        chapter_text = "\n".join(
            f"{v['verse']}. {v['text']}" for v in chapter["verses"]
        )
        prompt = (PROMPTS_DIR / f"{kind}.txt").read_text().format(
            chapter_ref=chapter_ref,
            work_title=source["title"],
            chapter_text=chapter_text,
            # Ask for extra so validation rejections still leave enough.
            n=gap["need"] + 2,
        ) + avoid_block(gap["avoid"])

        custom_id = f"{gap['book_slug']}--{gap['chapter']}--{kind}"
        meta[custom_id] = {"kind": kind, "chapter_ref": chapter_ref, "need": gap["need"]}
        requests.append(
            {
                "custom_id": custom_id,
                "params": {
                    "model": MODEL,
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                    "output_config": {
                        "format": {
                            "type": "json_schema",
                            "schema": api_json_schema(PAYLOAD_SCHEMAS[kind]),
                        }
                    },
                },
            }
        )
    return requests, meta


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--work", default="book-of-mormon")
    parser.add_argument("--target", type=int, default=4)
    parser.add_argument("--out", default="refill.jsonl")
    parser.add_argument(
        "--dry-run", action="store_true", help="Report gaps without generating"
    )
    args = parser.parse_args()

    gaps = fetch_gaps(args.work, args.target)
    print(
        f"{gaps['gap_count']} lessons below target {args.target}; "
        f"{gaps['missing_total']} exercises missing"
    )
    for gap in gaps["gaps"][:20]:
        print(f"  {gap['lesson_title']}: {gap['have']}/{args.target} (need {gap['need']})")
    if args.dry_run or gaps["gap_count"] == 0:
        return

    source = json.loads(Path(args.source).read_text())
    requests, meta = build_requests(source, gaps["gaps"])
    if not requests:
        print("Nothing to regenerate.")
        return

    client = anthropic.Anthropic(api_key=api_key())
    print(f"Submitting {len(requests)} regeneration requests via {MODEL}…")
    batch = client.messages.batches.create(requests=requests)
    while True:
        status = client.messages.batches.retrieve(batch.id)
        counts = status.request_counts
        print(
            f"  {status.processing_status}: ok={counts.succeeded} err={counts.errored}",
            flush=True,
        )
        if status.processing_status == "ended":
            break
        time.sleep(30)

    stats = {"valid": 0, "invalid": 0, "errored": 0}
    with Path(args.out).open("w") as out:
        for result in client.messages.batches.results(batch.id):
            if result.result.type != "succeeded":
                stats["errored"] += 1
                continue
            info = meta[result.custom_id]
            schema = PAYLOAD_SCHEMAS[info["kind"]]
            raw = "".join(
                b.text for b in result.result.message.content if b.type == "text"
            )
            try:
                parsed = schema.model_validate_json(raw)
            except Exception as exc:
                stats["invalid"] += 1
                print(f"  INVALID {result.custom_id}: {exc}", file=sys.stderr)
                continue
            for exercise in parsed.exercises:
                out.write(
                    json.dumps(
                        {
                            "custom_id": result.custom_id,
                            "kind": info["kind"],
                            "chapter_ref": info["chapter_ref"],
                            "model": MODEL,
                            "payload": exercise.model_dump(),
                        }
                    )
                    + "\n"
                )
                stats["valid"] += 1
    print(f"Done: {stats}  →  {args.out}")
    print(
        "Next: upload to the data bucket, then invoke import_exercises and "
        "validate_exercises. Duplicate payloads are skipped on import."
    )


if __name__ == "__main__":
    main()
