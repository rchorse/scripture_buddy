"""Friend requests, with dual consent and parental approval for minors.

Rules, in the order they are enforced:

1. Blocks win. A blocked pair cannot request in either direction.
2. Both learners must agree — a request is not a friendship.
3. If either learner is a minor, THAT learner's parent must also approve. A
   teen's friend accepting is not a substitute for a parent's approval.
4. Under-13 accounts have no social surface at all. Not gated, not
   configurable — the product decision is that a child's information is never
   visible to another user.

Rule 4 is why there is no `social` consent scope: consent is only meaningful
for something that can happen, and this cannot.
"""
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.core import FamilyMember, User
from app.models.social import Block, FriendRequest, Friendship, ParentApproval
from app.services import ages


class FriendshipError(ValueError):
    pass


def _ordered(a, b) -> tuple:
    return (a, b) if str(a) < str(b) else (b, a)


def is_blocked(db: Session, one, other) -> bool:
    return (
        db.scalar(
            select(Block).where(
                or_(
                    and_(Block.blocker_id == one, Block.blocked_id == other),
                    and_(Block.blocker_id == other, Block.blocked_id == one),
                )
            )
        )
        is not None
    )


def are_friends(db: Session, one, other) -> bool:
    a, b = _ordered(one, other)
    return (
        db.scalar(
            select(Friendship).where(Friendship.user_a == a, Friendship.user_b == b)
        )
        is not None
    )


def _bracket(user: User) -> str:
    if user.birth_date is None:
        return ages.ADULT
    return ages.bracket_for(user.birth_date, datetime.now(UTC).date())


def _parents_of(db: Session, child_id) -> list[User]:
    families = {
        m.family_id
        for m in db.scalars(
            select(FamilyMember).where(
                FamilyMember.user_id == child_id, FamilyMember.relation == "child"
            )
        )
    }
    if not families:
        return []
    return list(
        db.scalars(
            select(User)
            .join(FamilyMember, FamilyMember.user_id == User.id)
            .where(
                FamilyMember.family_id.in_(families),
                FamilyMember.relation == "parent",
            )
        )
    )


def assert_may_socialize(db: Session, user: User) -> None:
    """Whether this learner may take part in social features at all.

    Under-13 accounts never can. This is a fixed product decision, not a
    setting: no child's display name or progress is ever visible to another
    user. Teens may, but each individual friendship still needs their parent's
    approval.
    """
    if _bracket(user) == ages.UNDER_13:
        raise FriendshipError(
            "Friends and leaderboards are not available for accounts under 13."
        )


def send_request(db: Session, sender: User, recipient: User) -> FriendRequest:
    if sender.id == recipient.id:
        raise FriendshipError("You cannot add yourself.")
    assert_may_socialize(db, sender)
    assert_may_socialize(db, recipient)

    if is_blocked(db, sender.id, recipient.id):
        # Deliberately vague: revealing a block tells the sender they were
        # blocked, which invites retaliation.
        raise FriendshipError("This request cannot be sent.")
    if are_friends(db, sender.id, recipient.id):
        raise FriendshipError("You are already friends.")

    # An existing request the other way means they already asked — accept it.
    reverse = db.scalar(
        select(FriendRequest).where(
            FriendRequest.from_user_id == recipient.id,
            FriendRequest.to_user_id == sender.id,
            FriendRequest.status.in_(["pending", "awaiting_parent"]),
        )
    )
    if reverse is not None:
        return accept_request(db, reverse, sender)

    existing = db.scalar(
        select(FriendRequest).where(
            FriendRequest.from_user_id == sender.id,
            FriendRequest.to_user_id == recipient.id,
        )
    )
    if existing is not None and existing.status in ("pending", "awaiting_parent"):
        return existing
    if existing is not None:
        existing.status = "pending"
        existing.resolved_at = None
        db.flush()
        return existing

    request = FriendRequest(
        from_user_id=sender.id, to_user_id=recipient.id, status="pending"
    )
    db.add(request)
    db.flush()
    return request


def accept_request(db: Session, request: FriendRequest, accepter: User) -> FriendRequest:
    """The recipient agrees. Parental approvals may still be outstanding."""
    if request.to_user_id != accepter.id:
        raise FriendshipError("Only the recipient can accept this request.")
    if request.status not in ("pending", "awaiting_parent"):
        raise FriendshipError(f"This request is {request.status}.")

    sender = db.get(User, request.from_user_id)
    recipient = db.get(User, request.to_user_id)
    if is_blocked(db, sender.id, recipient.id):
        raise FriendshipError("This request cannot be accepted.")

    # Create an approval row for each side that is a minor.
    created_any = False
    for learner in (sender, recipient):
        if _bracket(learner) == ages.ADULT:
            continue
        for parent in _parents_of(db, learner.id):
            already = db.scalar(
                select(ParentApproval).where(
                    ParentApproval.request_id == request.id,
                    ParentApproval.child_user_id == learner.id,
                )
            )
            if already is None:
                db.add(
                    ParentApproval(
                        request_id=request.id,
                        child_user_id=learner.id,
                        parent_user_id=parent.id,
                    )
                )
                created_any = True
            break  # one approval per child is enough

    db.flush()
    if created_any or _outstanding_approvals(db, request):
        request.status = "awaiting_parent"
        return request

    return _finalize(db, request)


def _outstanding_approvals(db: Session, request: FriendRequest) -> list[ParentApproval]:
    return list(
        db.scalars(
            select(ParentApproval).where(
                ParentApproval.request_id == request.id,
                ParentApproval.decision == "pending",
            )
        )
    )


def decide_parent_approval(
    db: Session, approval: ParentApproval, parent: User, approve: bool
) -> FriendRequest:
    if approval.parent_user_id != parent.id:
        raise FriendshipError("You are not the approving parent for this request.")
    if approval.decision != "pending":
        raise FriendshipError(f"Already {approval.decision}.")

    approval.decision = "approved" if approve else "denied"
    approval.decided_at = datetime.now(UTC)
    request = db.get(FriendRequest, approval.request_id)

    if not approve:
        request.status = "declined"
        request.resolved_at = datetime.now(UTC)
        db.flush()
        return request

    db.flush()
    if _outstanding_approvals(db, request):
        return request  # still waiting on the other side's parent
    return _finalize(db, request)


def _finalize(db: Session, request: FriendRequest) -> FriendRequest:
    a, b = _ordered(request.from_user_id, request.to_user_id)
    if not are_friends(db, a, b):
        db.add(Friendship(user_a=a, user_b=b))
    request.status = "accepted"
    request.resolved_at = datetime.now(UTC)
    db.flush()
    return request


def decline_request(db: Session, request: FriendRequest, actor: User) -> FriendRequest:
    if actor.id not in (request.to_user_id, request.from_user_id):
        raise FriendshipError("Not your request.")
    request.status = "declined" if actor.id == request.to_user_id else "cancelled"
    request.resolved_at = datetime.now(UTC)
    db.flush()
    return request


def unfriend(db: Session, one, other) -> None:
    a, b = _ordered(one, other)
    friendship = db.scalar(
        select(Friendship).where(Friendship.user_a == a, Friendship.user_b == b)
    )
    if friendship is not None:
        db.delete(friendship)
    # Clear any historical requests so they can reconnect later.
    for request in db.scalars(
        select(FriendRequest).where(
            or_(
                and_(
                    FriendRequest.from_user_id == one, FriendRequest.to_user_id == other
                ),
                and_(
                    FriendRequest.from_user_id == other, FriendRequest.to_user_id == one
                ),
            )
        )
    ):
        request.status = "cancelled"
        request.resolved_at = datetime.now(UTC)


def block(db: Session, blocker: User, blocked_id) -> Block:
    """Blocking also severs any existing friendship and pending requests."""
    if blocker.id == blocked_id:
        raise FriendshipError("You cannot block yourself.")
    unfriend(db, blocker.id, blocked_id)
    existing = db.scalar(
        select(Block).where(
            Block.blocker_id == blocker.id, Block.blocked_id == blocked_id
        )
    )
    if existing is not None:
        return existing
    row = Block(blocker_id=blocker.id, blocked_id=blocked_id)
    db.add(row)
    db.flush()
    return row


def friends_of(db: Session, user_id) -> list:
    """Ids of everyone this user is friends with."""
    out = []
    for row in db.scalars(
        select(Friendship).where(
            or_(Friendship.user_a == user_id, Friendship.user_b == user_id)
        )
    ):
        out.append(row.user_b if row.user_a == user_id else row.user_a)
    return out
