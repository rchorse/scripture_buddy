# ScriptureBuddy infra (CDK)

Five stacks: `ScriptureBuddyAuth`, `ScriptureBuddyApi`, `ScriptureBuddyJobs`, `ScriptureBuddyCerts` (us-east-1, only when `web_domain` context is set), `ScriptureBuddyWeb`.

## Shared infrastructure

The API Lambda joins BlahBlahBudget's VPC and reuses its Lambda security group (which already has ingress to the shared Aurora Serverless v2 cluster). There is **no database stack here** — ScriptureBuddy owns a separate `scripturebuddy` database + `sb_app` role on that cluster.

Fill the `FILL_ME` context values in `cdk.json` once (each contains the AWS CLI command that prints it).

## First deploy

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
cdk deploy ScriptureBuddyAuth ScriptureBuddyApi ScriptureBuddyJobs ScriptureBuddyWeb
```

## One-time database bootstrap

After the first `ScriptureBuddyApi` deploy:

```bash
aws lambda invoke --function-name scripturebuddy-api \
  --cli-binary-format raw-in-base64-out \
  --payload '{"task":"bootstrap_db"}' /dev/stdout
```

This creates the `scripturebuddy` database and `sb_app` role using the cluster
admin secret, and writes sb_app's credentials into `scripturebuddy/db-credentials`.
Idempotent. Then apply migrations:

```bash
aws lambda invoke --function-name scripturebuddy-api \
  --cli-binary-format raw-in-base64-out \
  --payload '{"task":"migrate"}' /dev/stdout
```

## DNS (Cloudflare)

Same rules as BlahBlahBudget: the `api` CNAME must be **DNS only (grey cloud)** —
API Gateway breaks behind the Cloudflare proxy. The web CNAME points at the
CloudFront distribution domain.
