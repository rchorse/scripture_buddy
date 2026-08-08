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

        # The admin UI is a different app on the API host. Without this, /admin
        # on the web domain falls through the SPA rule below and quietly serves
        # the learner app instead — the most confusing possible outcome, since
        # it looks like the admin simply isn't there.
        admin_redirect = None
        if domain_name:
            api_host = f"api.{domain_name}"
            admin_redirect = cloudfront.Function(
                self,
                "AdminRedirect",
                comment=f"Redirect /admin* to https://{api_host}",
                code=cloudfront.FunctionCode.from_inline(
                    """
function handler(event) {
  var uri = event.request.uri;
  var qs = event.request.querystring || {};
  var query = Object.keys(qs)
    .map(function (k) {
      return qs[k].value ? k + '=' + qs[k].value : k;
    })
    .join('&');
  return {
    statusCode: 302,
    statusDescription: 'Found',
    headers: {
      location: { value: 'https://__API_HOST__' + uri + (query ? '?' + query : '') },
    },
  };
}
""".replace("__API_HOST__", api_host)
                ),
                runtime=cloudfront.FunctionRuntime.JS_2_0,
            )

        self.distribution = cloudfront.Distribution(
            self,
            "Distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(self.bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            additional_behaviors={
                "/admin*": cloudfront.BehaviorOptions(
                    origin=origins.S3BucketOrigin.with_origin_access_control(self.bucket),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    function_associations=[
                        cloudfront.FunctionAssociation(
                            function=admin_redirect,
                            event_type=cloudfront.FunctionEventType.VIEWER_REQUEST,
                        )
                    ],
                ),
            }
            if admin_redirect
            else {},
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
            # `www` is a SAN on the same certificate, so serve it here rather
            # than leaving people who type it on an error page.
            domain_names=[domain_name, f"www.{domain_name}"] if domain_name else None,
            certificate=certificate,
        )

        CfnOutput(self, "BucketName", value=self.bucket.bucket_name)
        CfnOutput(self, "DistributionDomain", value=self.distribution.distribution_domain_name)
        CfnOutput(self, "DistributionId", value=self.distribution.distribution_id)
