import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.principal import get_current_user, require_adult
from app.models.core import User
from app.models.social import Block, FriendRequest, ParentApproval
from app.services import friendships, name_moderation
from app.services.friendships import FriendshipError

router = APIRouter(prefix="/social", tags=["social"])


def _public(db: Session, user_id) -> dict:
    user = db.get(User, user_id)
    if user is None:
        return {"user_id": str(user_id), "name": "(removed)"}
    return {"user_id": str(user.id), "name": name_moderation.public_name(user)}


@router.get("/me")
def my_social(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Friends, pending requests, and whether this account may socialize."""
    try:
        friendships.assert_may_socialize(db, user)
        allowed, reason = True, ""
    except FriendshipError as exc:
        allowed, reason = False, str(exc)

    incoming = db.scalars(
        select(FriendRequest).where(
            FriendRequest.to_user_id == user.id,
            FriendRequest.status.in_(["pending", "awaiting_parent"]),
        )
    ).all()
    outgoing = db.scalars(
        select(FriendRequest).where(
            FriendRequest.from_user_id == user.id,
            FriendRequest.status.in_(["pending", "awaiting_parent"]),
        )
    ).all()

    return {
        "may_socialize": allowed,
        "reason": reason,
        "display_name": name_moderation.public_name(user),
        "display_name_status": user.display_name_status,
        "friends": [_public(db, fid) for fid in friendships.friends_of(db, user.id)],
        "incoming_requests": [
            {"id": str(r.id), "status": r.status, **_public(db, r.from_user_id)}
            for r in incoming
        ],
        "outgoing_requests": [
            {"id": str(r.id), "status": r.status, **_public(db, r.to_user_id)}
            for r in outgoing
        ],
    }


@router.put("/display-name")
def set_display_name(
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Set a display name, screened before anyone else can see it.

    Screening is fail-closed: an undecided name is stored but not shown, and
    the username is displayed until it clears.
    """
    from app.core.principal import bracket_of
    from app.services import ages

    name = (body.get("display_name") or "").strip()
    is_child = bracket_of(user) == ages.UNDER_13
    verdict = name_moderation.screen(name, is_child=is_child)

    if verdict["status"] == name_moderation.FLAGGED:
        raise HTTPException(status_code=400, detail=verdict["reason"])

    user.display_name = name
    user.display_name_status = verdict["status"]
    db.commit()
    return {
        "display_name": name,
        "status": verdict["status"],
        "shown_as": name_moderation.public_name(user),
        "note": verdict["reason"] or "",
    }


@router.post("/requests")
def send_friend_request(
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    username = (body.get("username") or "").strip().lower()
    target = db.scalar(select(User).where(User.username == username))
    if target is None or target.status != "active":
        raise HTTPException(status_code=404, detail="No such learner.")
    try:
        request = friendships.send_request(db, user, target)
    except FriendshipError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return {"id": str(request.id), "status": request.status}


@router.post("/requests/{request_id}/accept")
def accept(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    request = db.get(FriendRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404)
    try:
        friendships.accept_request(db, request, user)
    except FriendshipError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return {
        "status": request.status,
        "note": (
            "A parent needs to approve this before you become friends."
            if request.status == "awaiting_parent"
            else ""
        ),
    }


@router.post("/requests/{request_id}/decline")
def decline(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    request = db.get(FriendRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404)
    try:
        friendships.decline_request(db, request, user)
    except FriendshipError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return {"status": request.status}


@router.get("/approvals")
def pending_approvals(
    db: Session = Depends(get_db),
    parent: User = Depends(require_adult),
):
    """Friend requests waiting on this parent's decision."""
    rows = db.scalars(
        select(ParentApproval).where(
            ParentApproval.parent_user_id == parent.id,
            ParentApproval.decision == "pending",
        )
    ).all()
    out = []
    for approval in rows:
        request = db.get(FriendRequest, approval.request_id)
        other_id = (
            request.to_user_id
            if request.from_user_id == approval.child_user_id
            else request.from_user_id
        )
        out.append(
            {
                "approval_id": str(approval.id),
                "child": _public(db, approval.child_user_id),
                "would_befriend": _public(db, other_id),
            }
        )
    return out


@router.post("/approvals/{approval_id}")
def decide_approval(
    approval_id: uuid.UUID,
    body: dict,
    db: Session = Depends(get_db),
    parent: User = Depends(require_adult),
):
    approval = db.get(ParentApproval, approval_id)
    if approval is None:
        raise HTTPException(status_code=404)
    try:
        request = friendships.decide_parent_approval(
            db, approval, parent, approve=bool(body.get("approve"))
        )
    except FriendshipError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return {"decision": approval.decision, "request_status": request.status}


@router.delete("/friends/{other_id}")
def remove_friend(
    other_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    friendships.unfriend(db, user.id, other_id)
    db.commit()
    return {"status": "removed"}


@router.post("/blocks")
def block_user(
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Blocking severs any friendship and prevents future requests."""
    target_id = body.get("user_id")
    if not target_id:
        raise HTTPException(status_code=400, detail="user_id required")
    try:
        friendships.block(db, user, uuid.UUID(str(target_id)))
    except (FriendshipError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return {"status": "blocked"}


@router.delete("/blocks/{other_id}")
def unblock(
    other_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.scalar(
        select(Block).where(Block.blocker_id == user.id, Block.blocked_id == other_id)
    )
    if row is not None:
        db.delete(row)
        db.commit()
    return {"status": "unblocked"}


@router.get("/leaderboard")
def leaderboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """This week's XP among the learner and their friends.

    Friends-only rather than global: a leaderboard of strangers is the one
    place a child's name would reach people their parent never approved.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import func

    from app.models.game import XpEvent

    try:
        friendships.assert_may_socialize(db, user)
    except FriendshipError as exc:
        return {"available": False, "reason": str(exc), "rows": []}

    week_start = datetime.now(UTC) - timedelta(days=7)
    ids = [user.id, *friendships.friends_of(db, user.id)]
    totals = dict(
        db.execute(
            select(XpEvent.user_id, func.coalesce(func.sum(XpEvent.amount), 0))
            .where(XpEvent.user_id.in_(ids), XpEvent.awarded_at >= week_start)
            .group_by(XpEvent.user_id)
        ).all()
    )
    rows = sorted(
        (
            {**_public(db, uid), "xp": int(totals.get(uid, 0)), "is_you": uid == user.id}
            for uid in ids
        ),
        key=lambda r: -r["xp"],
    )
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return {"available": True, "reason": "", "rows": rows}
