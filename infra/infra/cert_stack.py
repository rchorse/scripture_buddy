from aws_cdk import (
    Stack,
    aws_certificatemanager as acm,
    CfnOutput,
)
from constructs import Construct


class CertStack(Stack):
    """CloudFront certificate — must live in us-east-1.

    Consumed by WebStack via cross_region_references=True (same pattern as
    BlahBlahBudget's CertStack).
    """

    def __init__(self, scope: Construct, construct_id: str, domain_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.certificate = acm.Certificate(
            self,
            "WebCert",
            domain_name=domain_name,
            validation=acm.CertificateValidation.from_dns(),
        )

        CfnOutput(self, "CertificateArn", value=self.certificate.certificate_arn)
