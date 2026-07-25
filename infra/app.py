#!/usr/bin/env python3
import os

import aws_cdk as cdk

from infra.auth_stack import AuthStack
from infra.api_stack import ApiStack
from infra.jobs_stack import JobsStack
from infra.cert_stack import CertStack
from infra.web_stack import WebStack

app = cdk.App()

env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region="us-west-2",
)
env_use1 = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region="us-east-1",
)

web_domain = app.node.try_get_context("web_domain")  # e.g. scripturebuddy.com
api_domain = app.node.try_get_context("api_domain")  # e.g. api.scripturebuddy.com

auth = AuthStack(app, "ScriptureBuddyAuth", env=env)
api = ApiStack(app, "ScriptureBuddyApi", auth=auth, custom_domain=api_domain, env=env)
jobs = JobsStack(app, "ScriptureBuddyJobs", api=api, env=env)

if web_domain:
    certs = CertStack(
        app,
        "ScriptureBuddyCerts",
        domain_name=web_domain,
        env=env_use1,
        cross_region_references=True,
    )
    WebStack(
        app,
        "ScriptureBuddyWeb",
        domain_name=web_domain,
        certificate=certs.certificate,
        env=env,
        cross_region_references=True,
    )
else:
    WebStack(app, "ScriptureBuddyWeb", env=env)

app.synth()
