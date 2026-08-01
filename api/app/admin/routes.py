import json
import os

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.admin.auth import COOKIE_NAME, cognito_login, require_owner
from app.core.db import get_db
from app.models.content import Exercise, ExerciseFlag, Lesson, Release, ReleaseItem, Work
from app.services.releases import cut_release

router = APIRouter(prefix="/admin", include_in_schema=False)

# API Gateway serves the app under a stage prefix (/prod) until a custom domain
# exists; every absolute URL the admin emits must carry it.
BASE = os.environ.get("URL_PREFIX", "")

templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)
templates.env.globals["base"] = BASE


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    try:
        token = cognito_login(username, password)
    except HTTPException:
        return templates.TemplateResponse(
            request, "login.html", {"error": "Invalid credentials"}, status_code=401
        )
    response = RedirectResponse(f"{BASE}/admin", status_code=303)
    response.set_cookie(
        COOKIE_NAME, token, httponly=True, secure=True, samesite="lax", max_age=3600
    )
    return response


@router.get("", response_class=HTMLResponse)
def dashboard(
    request: Request,
    claims: dict = Depends(require_owner),
    db: Session = Depends(get_db),
):
    works = db.scalars(select(Work).order_by(Work.title)).all()
    rows = []
    for work in works:
        state_counts = dict(
            db.execute(
                select(Exercise.state, func.count())
                .join(Lesson, Exercise.lesson_id == Lesson.id)
                .where(Lesson.work_id == work.id)
                .group_by(Exercise.state)
            ).all()
        )
        # What learners can actually see: the size of the LATEST release, not
        # the cumulative total across every release ever cut.
        latest_release_id = db.scalar(
            select(Release.id)
            .where(Release.work_id == work.id)
            .order_by(Release.version.desc())
            .limit(1)
        )
        live_items = (
            db.scalar(
                select(func.count())
                .select_from(ReleaseItem)
                .where(ReleaseItem.release_id == latest_release_id)
            )
            if latest_release_id
            else 0
        )
        # Approved work that hasn't been published yet — the actionable number.
        unreleased = db.scalar(
            select(func.count())
            .select_from(Exercise)
            .join(Lesson, Exercise.lesson_id == Lesson.id)
            .where(
                Lesson.work_id == work.id,
                Exercise.state == "approved",
                ~Exercise.id.in_(
                    select(ReleaseItem.exercise_id).where(
                        ReleaseItem.release_id == latest_release_id
                    )
                )
                if latest_release_id
                else True,
            )
        )
        rows.append(
            {
                "slug": work.slug,
                "title": work.title,
                "status": work.status,
                "drafts": state_counts.get("ai_draft", 0),
                "in_review": state_counts.get("in_review", 0),
                "approved": state_counts.get("approved", 0),
                "live_items": live_items or 0,
                "unreleased": unreleased or 0,
            }
        )
    return templates.TemplateResponse(request, "dashboard.html", {"works": rows})


def _work_or_404(db: Session, slug: str) -> Work:
    work = db.scalar(select(Work).where(Work.slug == slug))
    if work is None:
        raise HTTPException(status_code=404)
    return work


@router.get("/works", response_class=HTMLResponse)
def works_index(request: Request, claims: dict = Depends(require_owner)):
    return RedirectResponse(f"{BASE}/admin", status_code=303)


@router.get("/works/{slug}", response_class=HTMLResponse)
def work_detail(
    slug: str,
    request: Request,
    claims: dict = Depends(require_owner),
    db: Session = Depends(get_db),
):
    work = _work_or_404(db, slug)
    latest_release_id = db.scalar(
        select(Release.id)
        .where(Release.work_id == work.id)
        .order_by(Release.version.desc())
        .limit(1)
    )
    in_latest = (
        select(ReleaseItem.exercise_id).where(ReleaseItem.release_id == latest_release_id)
        if latest_release_id
        else None
    )

    # What cutting a release would actually change, rather than the total.
    approved_q = (
        select(func.count())
        .select_from(Exercise)
        .join(Lesson, Exercise.lesson_id == Lesson.id)
        .where(Lesson.work_id == work.id, Exercise.state == "approved")
    )
    if in_latest is None:
        new_count = db.scalar(approved_q)
        removed_count = 0
    else:
        new_count = db.scalar(approved_q.where(~Exercise.id.in_(in_latest)))
        # Items in the live release that are no longer approved (retired or
        # rejected since) would drop out of the next release.
        removed_count = db.scalar(
            select(func.count())
            .select_from(ReleaseItem)
            .join(Exercise, Exercise.id == ReleaseItem.exercise_id)
            .where(
                ReleaseItem.release_id == latest_release_id,
                Exercise.state != "approved",
            )
        )
    releases = [
        {
            "version": r.version,
            "released_at": r.released_at.strftime("%Y-%m-%d %H:%M"),
            # NOT "items" — Jinja resolves dict.items to the built-in method.
            "item_count": db.scalar(
                select(func.count())
                .select_from(ReleaseItem)
                .where(ReleaseItem.release_id == r.id)
            ),
        }
        for r in db.scalars(
            select(Release).where(Release.work_id == work.id).order_by(Release.version.desc())
        )
    ]
    return templates.TemplateResponse(
        request,
        "work_detail.html",
        {
            "work": work,
            "new_count": new_count or 0,
            "removed_count": removed_count or 0,
            "releases": releases,
        },
    )


@router.post("/works/{slug}/status")
def set_status(
    slug: str,
    status: str = Form(...),
    claims: dict = Depends(require_owner),
    db: Session = Depends(get_db),
):
    if status not in ("draft", "released"):
        raise HTTPException(status_code=400)
    work = _work_or_404(db, slug)
    work.status = status
    db.commit()
    return RedirectResponse(f"{BASE}/admin/works/{slug}", status_code=303)


@router.post("/works/{slug}/cut-release")
def cut_release_route(
    slug: str,
    claims: dict = Depends(require_owner),
    db: Session = Depends(get_db),
):
    work = _work_or_404(db, slug)
    cut_release(db, work)
    return RedirectResponse(f"{BASE}/admin/works/{slug}", status_code=303)


@router.get("/review", response_class=HTMLResponse)
def review_queue(
    request: Request,
    claims: dict = Depends(require_owner),
    db: Session = Depends(get_db),
):
    pending = db.execute(
        select(Exercise, Lesson.title)
        .join(Lesson, Exercise.lesson_id == Lesson.id)
        .where(Exercise.state.in_(["ai_draft", "in_review"]))
        .order_by(Lesson.position, Exercise.kind)
        .limit(25)
    ).all()
    total = db.scalar(
        select(func.count())
        .select_from(Exercise)
        .where(Exercise.state.in_(["ai_draft", "in_review"]))
    )
    exercises = [
        {
            "id": str(ex.id),
            "kind": ex.kind,
            "difficulty": ex.difficulty,
            "state": ex.state,
            "lesson_title": lesson_title,
            "review_note": ex.review_note,
            "payload_json": json.dumps(ex.payload, indent=2, ensure_ascii=False),
        }
        for ex, lesson_title in pending
    ]
    return templates.TemplateResponse(
        request, "review.html", {"exercises": exercises, "total": total or 0}
    )


@router.get("/flags", response_class=HTMLResponse)
def flags_queue(
    request: Request,
    claims: dict = Depends(require_owner),
    db: Session = Depends(get_db),
):
    counts = (
        select(
            ExerciseFlag.exercise_id.label("exercise_id"),
            func.count().label("flag_count"),
        )
        .where(ExerciseFlag.resolved_at.is_(None))
        .group_by(ExerciseFlag.exercise_id)
        .subquery()
    )
    pending = db.execute(
        select(Exercise, Lesson.title, counts.c.flag_count)
        .join(Lesson, Exercise.lesson_id == Lesson.id)
        .join(counts, counts.c.exercise_id == Exercise.id)
        .order_by(counts.c.flag_count.desc())
        .limit(50)
    ).all()

    rows = []
    for exercise, lesson_title, flag_count in pending:
        flags = db.scalars(
            select(ExerciseFlag)
            .where(
                ExerciseFlag.exercise_id == exercise.id,
                ExerciseFlag.resolved_at.is_(None),
            )
            .order_by(ExerciseFlag.created_at)
        ).all()
        rows.append(
            {
                "id": str(exercise.id),
                "kind": exercise.kind,
                "state": exercise.state,
                "lesson_title": lesson_title,
                "flag_count": flag_count,
                "payload_json": json.dumps(exercise.payload, indent=2, ensure_ascii=False),
                "flags": [
                    {
                        "reason": f.reason,
                        "note": f.note,
                        "created_at": f.created_at.strftime("%Y-%m-%d %H:%M"),
                    }
                    for f in flags
                ],
            }
        )
    return templates.TemplateResponse(
        request,
        "flags.html",
        {"rows": rows, "total": len(rows)},
    )


@router.post("/flags/{exercise_id}/resolve", response_class=HTMLResponse)
def resolve_flags(
    exercise_id: str,
    request: Request,
    action: str = Form(...),
    claims: dict = Depends(require_owner),
    db: Session = Depends(get_db),
):
    exercise = db.get(Exercise, exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404)
    if action not in ("retire", "dismiss"):
        raise HTTPException(status_code=400)
    db.execute(
        update(ExerciseFlag)
        .where(
            ExerciseFlag.exercise_id == exercise.id,
            ExerciseFlag.resolved_at.is_(None),
        )
        .values(resolved_at=func.now())
    )
    if action == "retire":
        exercise.state = "retired"
        exercise.review_note = "retired by owner after learner flags"
    else:
        exercise.state = "approved"
        exercise.review_note = "flags dismissed by owner"
    lesson_title = db.get(Lesson, exercise.lesson_id).title
    db.commit()
    return templates.TemplateResponse(
        request,
        "_flag_done.html",
        {"lesson_title": lesson_title, "kind": exercise.kind, "state": exercise.state},
    )


@router.post("/exercises/{exercise_id}/decide", response_class=HTMLResponse)
def decide_exercise(
    exercise_id: str,
    request: Request,
    decision: str = Form(...),
    payload: str = Form(...),
    review_note: str = Form(""),
    claims: dict = Depends(require_owner),
    db: Session = Depends(get_db),
):
    exercise = db.get(Exercise, exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404)
    if decision not in ("approve", "reject"):
        raise HTTPException(status_code=400)
    try:
        exercise.payload = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Payload is not valid JSON")
    exercise.state = "approved" if decision == "approve" else "rejected"
    exercise.review_note = review_note
    exercise.created_by = "owner" if decision == "approve" else exercise.created_by
    lesson_title = db.get(Lesson, exercise.lesson_id).title
    db.commit()
    return templates.TemplateResponse(
        request,
        "_exercise_done.html",
        {"lesson_title": lesson_title, "kind": exercise.kind, "state": exercise.state},
    )
