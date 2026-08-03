import os
import shutil
import subprocess
import sys

import jsii
from aws_cdk import (
    BundlingOptions,
    ILocalBundling,
    Stack,
    aws_lambda as lambda_,
    aws_apigateway as apigw,
    aws_certificatemanager as acm,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_events as events,
    aws_events_targets as targets,
    aws_s3 as s3,
    aws_secretsmanager as secretsmanager,
    Duration,
    CfnOutput,
    RemovalPolicy,
)
from constructs import Construct

from infra.auth_stack import AuthStack

# Absolute path to the api/ directory (one level up from infra/)
_API_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "api"))

_BUNDLE_EXCLUDE = {".venv", ".venv-deps", "__pycache__", "dev.db", ".gitkeep", "tests"}

# Trimmed from the installed dependencies to stay under Lambda's 250MB
# unzipped limit. boto3/botocore are supplied by the Python runtime, and `bin`
# holds console scripts that never execute in Lambda.
_PRUNE_FROM_BUNDLE = ("boto3", "botocore", "bin", "pip", "setuptools", "wheel")


def _prune(output_dir: str) -> None:
    """Drop what Lambda already provides or never runs there."""
    for name in _PRUNE_FROM_BUNDLE:
        target = os.path.join(output_dir, name)
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)
    # Distribution metadata for pruned packages, plus stray caches.
    for entry in os.listdir(output_dir):
        if entry.endswith((".dist-info", ".egg-info")) and entry.split("-")[0] in (
            _PRUNE_FROM_BUNDLE
        ):
            shutil.rmtree(os.path.join(output_dir, entry), ignore_errors=True)


@jsii.implements(ILocalBundling)
class _LocalPipBundler:
    """Installs pip requirements and copies source into the CDK asset output dir."""

    def try_bundle(self, output_dir: str, *, options: BundlingOptions = None) -> bool:
        try:
            subprocess.run(
                [
                    sys.executable, "-m", "pip", "install",
                    "-r", os.path.join(_API_DIR, "requirements.txt"),
                    "-t", output_dir,
                    "--platform", "manylinux2014_x86_64",
                    "--python-version", "3.13",
                    "--only-binary", ":all:",
                    "--quiet",
                ],
                check=True,
            )
            _prune(output_dir)
            for item in os.listdir(_API_DIR):
                if item in _BUNDLE_EXCLUDE:
                    continue
                src = os.path.join(_API_DIR, item)
                dst = os.path.join(output_dir, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
            return True
        except Exception as exc:
            print(f"Local bundling failed: {exc}")
            return False


class ApiStack(Stack):
    """Lambda (FastAPI via Mangum) + API Gateway REST API.

    No database stack of its own: the Lambda joins BlahBlahBudget's VPC and
    reuses its lambda security group (which already has ingress to the shared
    Aurora cluster). The shared-infra identifiers come from cdk.json context:
      shared_vpc_name, shared_lambda_sg_id, shared_db_host, shared_admin_secret_arn
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        auth: AuthStack,
        custom_domain: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vpc = ec2.Vpc.from_lookup(
            self, "SharedVpc", vpc_name=self.node.try_get_context("shared_vpc_name")
        )
        lambda_sg = ec2.SecurityGroup.from_security_group_id(
            self, "SharedLambdaSg", self.node.try_get_context("shared_lambda_sg_id")
        )
        db_host = self.node.try_get_context("shared_db_host")
        consent_sender = self.node.try_get_context("consent_email_sender") or ""
        public_api_url = (
            f"https://{custom_domain}" if custom_domain else self.node.try_get_context("public_api_url") or ""
        )
        admin_secret_arn = self.node.try_get_context("shared_admin_secret_arn")

        # Staging bucket for content-pipeline payloads too large for a direct
        # Lambda invoke (scripture source JSON, generated exercise batches).
        self.data_bucket = s3.Bucket(
            self,
            "DataBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # ScriptureBuddy's own DB credentials (sb_app role), populated by the
        # one-time {"task":"bootstrap_db"} invoke.
        self.db_secret = secretsmanager.Secret(
            self,
            "DbSecret",
            secret_name="scripturebuddy/db-credentials",
            description="sb_app credentials for the scripturebuddy database",
        )

        self.api_function = lambda_.Function(
            self,
            "ApiFunction",
            function_name="scripturebuddy-api",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="main.handler",
            code=lambda_.Code.from_asset(
                _API_DIR,
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_13.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output --quiet"
                        " && cp -rT . /asset-output"
                        f" && cd /asset-output && rm -rf {' '.join(_BUNDLE_EXCLUDE)}"
                        f" {' '.join(_PRUNE_FROM_BUNDLE)}",
                    ],
                    local=_LocalPipBundler(),
                ),
            ),
            # Headroom for Aurora scale-to-zero resume and the migrate task.
            timeout=Duration.seconds(60),
            memory_size=1024,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[lambda_sg],
            environment={
                "USER_POOL_ID": auth.user_pool.user_pool_id,
                "USER_POOL_CLIENT_ID": auth.app_client.user_pool_client_id,
                "DB_SECRET_ARN": self.db_secret.secret_arn,
                "DB_HOST": db_host,
                "DB_NAME": "scripturebuddy",
                "BOOTSTRAP_ADMIN_SECRET_ARN": admin_secret_arn or "",
                "DATA_BUCKET": self.data_bucket.bucket_name,
                # Admin UI URL prefix: API GW stage until a custom domain exists.
                "URL_PREFIX": "/prod",
                # Public base for parent-facing consent links.
                "PUBLIC_API_URL": public_api_url,
                # Verified SES sender for consent email; blank disables sending.
                "CONSENT_EMAIL_SENDER": consent_sender,
            },
        )

        # Read for content payloads; write/delete for consent evidence, which
        # parents upload via presigned PUT and the retention sweep erases.
        self.data_bucket.grant_read_write(self.api_function)
        self.data_bucket.grant_delete(self.api_function)
        self.db_secret.grant_read(self.api_function)
        self.db_secret.grant_write(self.api_function)  # bootstrap writes sb_app creds

        if admin_secret_arn:
            admin_secret = secretsmanager.Secret.from_secret_complete_arn(
                self, "SharedAdminSecret", admin_secret_arn
            )
            admin_secret.grant_read(self.api_function)  # bootstrap only

        # Parents create child sign-ins (username-only, no email) and the
        # retention sweep deletes them. Scoped to this pool only.
        self.api_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "cognito-idp:AdminCreateUser",
                    "cognito-idp:AdminSetUserPassword",
                    "cognito-idp:AdminDeleteUser",
                    "cognito-idp:AdminGetUser",
                    "cognito-idp:ListUsers",
                ],
                resources=[auth.user_pool.user_pool_arn],
            )
        )

        # Display-name screening calls Haiku with this key. Created out of band
        # (see docs); referenced by name so a missing secret is a runtime
        # fail-closed rather than a deploy failure.
        self.api_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[
                    f"arn:aws:secretsmanager:{self.region}:{self.account}:"
                    "secret:scripturebuddy/anthropic-api-key-*"
                ],
            )
        )

        # Consent email to parents (email-plus verifiable consent).
        self.api_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail", "ses:SendRawEmail"],
                resources=["*"],
            )
        )

        # Keep one execution environment warm (cheaper than provisioned concurrency).
        warm_rule = events.Rule(
            self, "WarmRule", schedule=events.Schedule.rate(Duration.minutes(5))
        )
        warm_rule.add_target(
            targets.LambdaFunction(
                self.api_function,
                event=events.RuleTargetInput.from_object({"warmer": True}),
            )
        )

        self.api = apigw.RestApi(
            self,
            "RestApi",
            rest_api_name="scripturebuddy-api",
            description="ScriptureBuddy API",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=[
                    "Content-Type",
                    "Authorization",
                    "X-Amz-Date",
                    "X-Api-Key",
                ],
            ),
            deploy_options=apigw.StageOptions(stage_name="prod"),
        )

        proxy = self.api.root.add_resource("{proxy+}")
        lambda_integration = apigw.LambdaIntegration(self.api_function)
        self.api.root.add_method("ANY", lambda_integration)
        proxy.add_method("ANY", lambda_integration)

        CfnOutput(self, "ApiUrl", value=self.api.url)
        CfnOutput(self, "LambdaFunctionName", value=self.api_function.function_name)
        CfnOutput(self, "DataBucketName", value=self.data_bucket.bucket_name)

        if custom_domain:
            api_cert = acm.Certificate(
                self, "ApiCert",
                domain_name=custom_domain,
                validation=acm.CertificateValidation.from_dns(),
            )
            domain = apigw.DomainName(
                self, "CustomDomain",
                domain_name=custom_domain,
                certificate=api_cert,
                endpoint_type=apigw.EndpointType.REGIONAL,
            )
            domain.add_base_path_mapping(self.api)
            CfnOutput(
                self,
                "ApiCustomDomainTarget",
                value=domain.domain_name_alias_domain_name,
            )
