"""One-time database bootstrap on the shared Aurora cluster.

Invoked manually: aws lambda invoke --function-name scripturebuddy-api \
  --payload '{"task":"bootstrap_db"}' ...

Uses the cluster admin secret (BOOTSTRAP_ADMIN_SECRET_ARN) to create the
`scripturebuddy` database and the `sb_app` role, then stores sb_app's
generated password into the app secret (DB_SECRET_ARN). Idempotent.
"""
import json
import os
import secrets as pysecrets

import boto3


def bootstrap_database() -> dict:
    admin_secret_arn = os.environ.get("BOOTSTRAP_ADMIN_SECRET_ARN")
    app_secret_arn = os.environ.get("DB_SECRET_ARN")
    host = os.environ.get("DB_HOST")
    if not admin_secret_arn or not app_secret_arn or not host:
        raise RuntimeError(
            "BOOTSTRAP_ADMIN_SECRET_ARN, DB_SECRET_ARN and DB_HOST must be set"
        )

    sm = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "us-west-2"))
    admin = json.loads(sm.get_secret_value(SecretId=admin_secret_arn)["SecretString"])

    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    # Connect as cluster admin to the default database (CREATE DATABASE cannot
    # run inside a transaction block).
    conn = psycopg2.connect(
        host=host,
        port=admin.get("port", 5432),
        user=admin["username"],
        password=admin["password"],
        dbname="postgres",
        connect_timeout=30,
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    created = {"database": False, "role": False}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'sb_app'")
            role_exists = cur.fetchone() is not None
            password = None
            if not role_exists:
                password = pysecrets.token_urlsafe(32)
                cur.execute(
                    sql.SQL("CREATE ROLE sb_app LOGIN PASSWORD {}").format(
                        sql.Literal(password)
                    )
                )
                created["role"] = True

            cur.execute("SELECT 1 FROM pg_database WHERE datname = 'scripturebuddy'")
            if cur.fetchone() is None:
                cur.execute("CREATE DATABASE scripturebuddy OWNER sb_app")
                created["database"] = True
    finally:
        conn.close()

    if created["role"]:
        sm.put_secret_value(
            SecretId=app_secret_arn,
            SecretString=json.dumps(
                {
                    "username": "sb_app",
                    "password": password,
                    "host": host,
                    "port": 5432,
                    "dbname": "scripturebuddy",
                }
            ),
        )

    return {"status": "ok", "created": created}
