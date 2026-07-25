from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_certificatemanager as acm,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct


class WebStack(Stack):
    """S3 + CloudFront hosting for the Flutter web build.

    The build itself is produced by GitHub Actions (flutter build web) and
    synced to the bucket; this stack only owns the hosting resources.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        domain_name: str | None = None,
        certificate: acm.ICertificate | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.bucket = s3.Bucket(
            self,
            "WebBucket",
            bucket_name=None,  # let CFN generate a unique name
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.distribution = cloudfront.Distribution(
            self,
            "Distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(self.bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            default_root_object="index.html",
            # Flutter web is a SPA: route unknown paths back to index.html.
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403, response_http_status=200, response_page_path="/index.html"
                ),
                cloudfront.ErrorResponse(
                    http_status=404, response_http_status=200, response_page_path="/index.html"
                ),
            ],
            domain_names=[domain_name] if domain_name else None,
            certificate=certificate,
        )

        CfnOutput(self, "BucketName", value=self.bucket.bucket_name)
        CfnOutput(self, "DistributionDomain", value=self.distribution.distribution_domain_name)
        CfnOutput(self, "DistributionId", value=self.distribution.distribution_id)
