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

_BUNDLE_EXCLUDE = {".venv", "__pycache__", "dev.db", ".gitkeep", "tests"}


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
                        f" && cd /asset-output && rm -rf {' '.join(_BUNDLE_EXCLUDE)}",
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
            },
        )

        self.data_bucket.grant_read(self.api_function)
        self.db_secret.grant_read(self.api_function)
        self.db_secret.grant_write(self.api_function)  # bootstrap writes sb_app creds

        if admin_secret_arn:
            admin_secret = secretsmanager.Secret.from_secret_complete_arn(
                self, "SharedAdminSecret", admin_secret_arn
            )
            admin_secret.grant_read(self.api_function)  # bootstrap only

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
