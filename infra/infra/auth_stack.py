from aws_cdk import (
    Stack,
    aws_cognito as cognito,
    CfnOutput,
    Duration,
    RemovalPolicy,
)
from constructs import Construct


class AuthStack(Stack):
    """Cognito user pool for ScriptureBuddy.

    Separate from BlahBlahBudget's pool on purpose: child accounts sign in with
    username only (no email — COPPA data minimization), and a pool's sign-in
    options are immutable after creation.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name="scripturebuddy-users",
            # Username sign-in (children have no email). Adults may also use
            # email as an alias.
            sign_in_aliases=cognito.SignInAliases(username=True, email=True),
            self_sign_up_enabled=True,
            # Email optional at the pool level; enforcement that adults have one
            # (and children don't) lives in the API signup flow.
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=False, mutable=True),
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=False,
                require_uppercase=False,
                require_digits=False,
                require_symbols=False,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Group whose members can access /admin (the owner).
        cognito.CfnUserPoolGroup(
            self,
            "OwnerGroup",
            user_pool_id=self.user_pool.user_pool_id,
            group_name="owner",
            description="ScriptureBuddy owner/curator — full admin access",
        )

        self.app_client = self.user_pool.add_client(
            "AppClient",
            user_pool_client_name="scripturebuddy-app",
            auth_flows=cognito.AuthFlow(user_srp=True, user_password=True),
            id_token_validity=Duration.hours(1),
            access_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(90),
            prevent_user_existence_errors=True,
        )

        CfnOutput(self, "UserPoolId", value=self.user_pool.user_pool_id)
        CfnOutput(self, "AppClientId", value=self.app_client.user_pool_client_id)
