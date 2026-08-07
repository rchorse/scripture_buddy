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

        # DNS lives at Cloudflare, not Route 53, so validation records are added
        # by hand and this deploy blocks until they resolve. `www` is a SAN on
        # the same certificate rather than a second one — people type it.
        self.certificate = acm.Certificate(
            self,
            "WebCert",
            domain_name=domain_name,
            subject_alternative_names=[f"www.{domain_name}"],
            validation=acm.CertificateValidation.from_dns(),
        )

        CfnOutput(self, "CertificateArn", value=self.certificate.certificate_arn)
