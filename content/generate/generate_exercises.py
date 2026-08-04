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

Reads the API key from AWS Secrets Manager (scripturebuddy/anthropic-api-key),
falling back to the ANTHROPIC_API_KEY environment variable. Uses the
50%-discounted Batches API.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import anthropic
import boto3

from schemas import PAYLOAD_SCHEMAS, api_json_schema

SECRET_ID = "scripturebuddy/anthropic-api-key"


def api_key() -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    client = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "us-west-2"))
    secret = client.get_secret_value(SecretId=SECRET_ID)["SecretString"]
    # Accept either a bare key or {"api_key": "..."} shaped secret.
    try:
        return json.loads(secret)["api_key"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return secret.strip()

MODEL = "claude-opus-5"
PROMPTS_DIR = Path(__file__).parent / "prompts"


def chapter_requests(
    source: dict,
    book_filter: str | None,
    kinds: list[str],
    n: int,
    chapters_filter: set[int] | None = None,
    skip_books: set[str] = frozenset(),
    prompts_dir: Path = PROMPTS_DIR,
):
    work_title = source["title"]
    for book in source["books"]:
        if book_filter and book["book"] != book_filter:
            continue
        if book["book"] in skip_books:
            continue
        for chapter in book["chapters"]:
            if chapters_filter and chapter["chapter"] not in chapters_filter:
                continue
            chapter_ref = chapter.get("reference", f"{book['book']} {chapter['chapter']}")
            chapter_text = "\n".join(
                f"{v['verse']}. {v['text']}" for v in chapter["verses"]
            )
            for kind in kinds:
                prompt = (prompts_dir / f"{kind}.txt").read_text().format(
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
                            "schema": api_json_schema(schema),
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
    parser.add_argument(
        "--chapters", default=None, help="Limit to these chapter numbers, e.g. '1,5,32'"
    )
    parser.add_argument(
        "--skip-books",
        default=None,
        help="Comma-separated book titles to leave out, e.g. '1 Nephi' once it is done",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print what would be submitted and stop"
    )
    args = parser.parse_args()

    source = json.loads(Path(args.source).read_text())
    kinds = args.kinds.split(",")
    for kind in kinds:
        if kind not in PAYLOAD_SCHEMAS:
            sys.exit(f"Unknown kind: {kind}")

    chapters_filter = (
        {int(c) for c in args.chapters.split(",")} if args.chapters else None
    )
    skip_books = set(args.skip_books.split(",")) if args.skip_books else frozenset()
    reqs = list(
        chapter_requests(
            source, args.book, kinds, args.per_chapter, chapters_filter, skip_books
        )
    )
    if args.dry_run:
        print(f"Would submit {len(reqs)} requests ({args.kinds}) via {MODEL}:")
        for custom_id, _, chapter_ref, _ in reqs:
            print(f"  {custom_id}  ({chapter_ref})")
        return

    client = anthropic.Anthropic(api_key=api_key())
    print(f"Submitting batch: {len(reqs)} requests ({args.kinds}) via {MODEL}")
    batch_id, meta = build_batch(client, iter(reqs))
    print(f"Batch {batch_id} submitted; polling…")
    poll_batch(client, batch_id)
    stats = collect(client, batch_id, meta, Path(args.out))
    print(f"Done: {stats}  →  {args.out}")


if __name__ == "__main__":
    main()
