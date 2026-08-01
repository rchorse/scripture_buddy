#!/usr/bin/env python3
"""Generate draft exercises for a work via the Anthropic Message Batches API.

Usage:
  python3 generate_exercises.py --source ../sources/book-of-mormon.json \
      --book "1 Nephi" --kinds mcq,cloze --per-chapter 4 --out drafts.jsonl

Reads chapter text from the local source JSON (no DB access needed), submits
one batch request per (chapter, kind), polls until the batch completes,
validates every result against content/generate/schemas.py, and writes valid
exercises to a JSONL file ready for the {"task":"import_exercises"} Lambda
invoke (upload the JSONL to the data bucket first).

Requires ANTHROPIC_API_KEY. Uses the 50%-discounted Batches API; a full book
at 4 exercises/kind/chapter lands well under typical per-book budget.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import anthropic

from schemas import PAYLOAD_SCHEMAS

MODEL = "claude-opus-5"
PROMPTS_DIR = Path(__file__).parent / "prompts"


def chapter_requests(source: dict, book_filter: str | None, kinds: list[str], n: int):
    work_title = source["title"]
    for book in source["books"]:
        if book_filter and book["book"] != book_filter:
            continue
        for chapter in book["chapters"]:
            chapter_ref = chapter.get("reference", f"{book['book']} {chapter['chapter']}")
            chapter_text = "\n".join(
                f"{v['verse']}. {v['text']}" for v in chapter["verses"]
            )
            for kind in kinds:
                prompt = (PROMPTS_DIR / f"{kind}.txt").read_text().format(
                    chapter_ref=chapter_ref,
                    work_title=work_title,
                    chapter_text=chapter_text,
                    n=n,
                )
                custom_id = f"{book['lds_slug']}--{chapter['chapter']}--{kind}"
                yield custom_id, kind, chapter_ref, prompt


def build_batch(client: anthropic.Anthropic, requests_iter) -> tuple[str, dict]:
    """Submit the batch; returns (batch_id, meta by custom_id)."""
    meta = {}
    batch_requests = []
    for custom_id, kind, chapter_ref, prompt in requests_iter:
        meta[custom_id] = {"kind": kind, "chapter_ref": chapter_ref}
        schema = PAYLOAD_SCHEMAS[kind]
        batch_requests.append(
            {
                "custom_id": custom_id,
                "params": {
                    "model": MODEL,
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                    "output_config": {
                        "format": {
                            "type": "json_schema",
                            "schema": schema.model_json_schema(),
                        }
                    },
                },
            }
        )
    batch = client.messages.batches.create(requests=batch_requests)
    return batch.id, meta


def poll_batch(client: anthropic.Anthropic, batch_id: str) -> None:
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        counts = batch.request_counts
        print(
            f"  {batch.processing_status}: ok={counts.succeeded} err={counts.errored} "
            f"processing={counts.processing}",
            flush=True,
        )
        if batch.processing_status == "ended":
            return
        time.sleep(30)


def collect(client: anthropic.Anthropic, batch_id: str, meta: dict, out_path: Path) -> dict:
    stats = {"valid": 0, "invalid": 0, "errored": 0}
    with out_path.open("w") as out:
        for result in client.messages.batches.results(batch_id):
            if result.result.type != "succeeded":
                stats["errored"] += 1
                print(f"  ERRORED {result.custom_id}: {result.result.type}", file=sys.stderr)
                continue
            info = meta[result.custom_id]
            schema = PAYLOAD_SCHEMAS[info["kind"]]
            raw = "".join(
                block.text for block in result.result.message.content if block.type == "text"
            )
            try:
                batch_payload = schema.model_validate_json(raw)
            except Exception as exc:
                stats["invalid"] += 1
                print(f"  INVALID {result.custom_id}: {exc}", file=sys.stderr)
                continue
            for exercise in batch_payload.exercises:
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
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--book", default=None, help="Limit to one book title, e.g. '1 Nephi'")
    parser.add_argument("--kinds", default="mcq,cloze")
    parser.add_argument("--per-chapter", type=int, default=4)
    parser.add_argument("--out", default="drafts.jsonl")
    args = parser.parse_args()

    source = json.loads(Path(args.source).read_text())
    kinds = args.kinds.split(",")
    for kind in kinds:
        if kind not in PAYLOAD_SCHEMAS:
            sys.exit(f"Unknown kind: {kind}")

    client = anthropic.Anthropic()
    reqs = list(chapter_requests(source, args.book, kinds, args.per_chapter))
    print(f"Submitting batch: {len(reqs)} requests ({args.kinds}) via {MODEL}")
    batch_id, meta = build_batch(client, iter(reqs))
    print(f"Batch {batch_id} submitted; polling…")
    poll_batch(client, batch_id)
    stats = collect(client, batch_id, meta, Path(args.out))
    print(f"Done: {stats}  →  {args.out}")


if __name__ == "__main__":
    main()
