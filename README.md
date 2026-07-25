# ScriptureBuddy

A gamified scripture-reading app (web, iOS, Android) that helps people actually *learn* the scriptures — Duolingo-style streaks, XP, leagues, and spaced-repetition memorization. Pilot book: The Book of Mormon; the platform is scripture-agnostic and extensible to other works.

## Monorepo layout

| Dir | Contents |
|---|---|
| `app/` | Flutter client (single codebase: web, iOS, Android) |
| `api/` | Python FastAPI backend, deployed to AWS Lambda (Mangum) behind API Gateway. Owner admin UI at `/admin`. |
| `infra/` | AWS CDK (Python) — stacks `ScriptureBuddyAuth`, `ScriptureBuddyApi`, `ScriptureBuddyJobs`, `ScriptureBuddyCerts` (us-east-1), `ScriptureBuddyWeb` |
| `content/` | Content pipeline tooling: scripture ingestion + LLM exercise generation (runs locally/CI, not in Lambda) |
| `docs/` | Architecture, compliance (COPPA program, retention schedule, consent form), moderation playbook |

## Local development

```bash
# API
cd api && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt -r requirements-dev.txt
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/scripturebuddy uvicorn main:app --reload

# Tests
cd api && pytest
```

## Deployment

Pushed to `main` → GitHub Actions runs `cdk deploy`, applies Alembic migrations via a `{"task":"migrate"}` Lambda invoke, builds Flutter web, and syncs to S3/CloudFront. See `.github/workflows/deploy.yml`.

The database is a dedicated `scripturebuddy` database on a shared Aurora Serverless v2 cluster (account infra shared with a sibling project); the CDK `ScriptureBuddyApi` stack imports the existing VPC/security group via context values in `infra/cdk.json`.
