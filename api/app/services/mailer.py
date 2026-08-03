"""Transactional email via SES.

Only ever used for consent correspondence with a PARENT's email address. No
child account has an email, so nothing here can reach a child.

SES starts in sandbox mode, where it will only deliver to verified addresses.
Until production access is granted, `send` records what it would have sent and
reports `delivered: False` rather than raising — a delivery failure must never
lose a consent request, and the owner can re-send from the admin queue.
"""
import logging
import os

import boto3

logger = logging.getLogger(__name__)

SENDER = os.environ.get("CONSENT_EMAIL_SENDER", "")


def send(to_address: str, subject: str, body_text: str, body_html: str = "") -> dict:
    if not SENDER:
        logger.warning("CONSENT_EMAIL_SENDER unset; not sending %r", subject)
        return {"delivered": False, "reason": "sender_not_configured"}
    if not to_address:
        return {"delivered": False, "reason": "no_recipient"}

    client = boto3.client("ses", region_name=os.environ.get("AWS_REGION", "us-west-2"))
    body: dict = {"Text": {"Data": body_text, "Charset": "UTF-8"}}
    if body_html:
        body["Html"] = {"Data": body_html, "Charset": "UTF-8"}
    try:
        response = client.send_email(
            Source=SENDER,
            Destination={"ToAddresses": [to_address]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": body,
            },
        )
        return {"delivered": True, "message_id": response["MessageId"]}
    except Exception as exc:  # noqa: BLE001 — never lose a consent request
        logger.warning("SES send failed for %r: %s", subject, exc)
        return {"delivered": False, "reason": str(exc)[:200]}
