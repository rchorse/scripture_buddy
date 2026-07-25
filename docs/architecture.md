# Architecture

See the approved plan for full detail. Summary:

- **Clients**: one Flutter codebase (`app/`) → web (S3+CloudFront), Android, iOS (built via Codemagic).
- **API**: FastAPI on Lambda (Mangum) behind API Gateway (`api/`). Owner admin UI (Jinja2/HTMX) at `/admin` on the same Lambda. Jobs are EventBridge rules invoking the Lambda with `{"task": ...}` payloads.
- **Data**: Postgres database `scripturebuddy` on the shared Aurora Serverless v2 cluster (BlahBlahBudget account infra). Postgres schemas as module boundaries: `content`, `core`, `game`, `social`, `mod`, `srs`. Alembic owns DDL.
- **Auth**: dedicated Cognito pool; child accounts are username-only. Cognito group `owner` gates `/admin`.
- **Content pipeline** (`content/`): ingest public-domain scripture JSON → Claude Opus 5 (Batches API) drafts exercises → owner review in admin → versioned releases. Clients only see released content.
- **No chat/messaging** — permanent product decision. Only user-visible UGC is display names (Haiku 4.5 pre-check, fail-closed, report/block).
- **COPPA**: under-13 supported; parent-created accounts, signed-form verifiable consent, per-scope consent records, deletion sweep. Compliance docs in `docs/compliance/`.
