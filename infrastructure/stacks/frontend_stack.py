from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_s3_deployment as s3deploy,
    RemovalPolicy,
    CfnOutput,
    Duration,
    Tags
)
from constructs import Construct
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.tags import get_service_specific_tags, validate_tags

class FrontendStack(Stack):
    
    def __init__(self, scope: Construct, construct_id: str, api_gateway, environment: str = 'dev', **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.api_gateway = api_gateway
        self.deployment_env = environment
        
        # S3 bucket for static website hosting
        self.website_bucket = s3.Bucket(
            self, 'WebsiteBucket',
            bucket_name=f'archlens-frontend-{self.account}-{self.region}',
            versioned=False,
            public_read_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.DESTROY  # For development
        )
        
        # Add tags for Frontend S3 bucket
        frontend_s3_tags = get_service_specific_tags(
            'Frontend-Website-Hosting',
            'frontend',
            {
                'DataType': 'Static-Website-Assets',
                'ContentType': 'HTML-CSS-JS-Assets'
            }
        )
        
        for key, value in validate_tags(frontend_s3_tags).items():
            Tags.of(self.website_bucket).add(key, value)
        
        # Origin Access Identity for CloudFront
        origin_access_identity = cloudfront.OriginAccessIdentity(
            self, 'OriginAccessIdentity'
        )
        
        # Add tags for Origin Access Identity
        oai_tags = get_service_specific_tags(
            'CloudFront-Origin-Access-Identity',
            'frontend',
            {
                'AccessControlType': 'Origin-Access-Identity',
                'SecurityFunction': 'S3-Access-Control'
            }
        )
        
        for key, value in validate_tags(oai_tags).items():
            Tags.of(origin_access_identity).add(key, value)
        
        # Grant read permissions to CloudFront
        self.website_bucket.grant_read(origin_access_identity)
        
        # CloudFront distribution
        self.distribution = cloudfront.Distribution(
            self, 'Distribution',
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(
                    self.website_bucket,
                    origin_access_identity=origin_access_identity
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
                compress=True,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED
            ),
            additional_behaviors={
                # API proxy behavior
                '/api/*': cloudfront.BehaviorOptions(
                    origin=origins.RestApiOrigin(api_gateway),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN
                )
            },
            default_root_object='index.html',
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path='/index.html',
                    ttl=Duration.seconds(300)
                ),
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path='/index.html',
                    ttl=Duration.seconds(300)
                )
            ],
            price_class=cloudfront.PriceClass.PRICE_CLASS_100  # Cost optimization
        )
        
        # Add tags for CloudFront Distribution
        cloudfront_tags = get_service_specific_tags(
            'Frontend-CloudFront-Distribution',
            'frontend',
            {
                'DistributionType': 'Web-Distribution',
                'PriceClass': 'PriceClass100'
            }
        )
        
        for key, value in validate_tags(cloudfront_tags).items():
            Tags.of(self.distribution).add(key, value)
        
        # Outputs
        CfnOutput(
            self, 'WebsiteURL',
            value=f'https://{self.distribution.distribution_domain_name}',
            description='ArchLens Frontend URL'
        )
        
        CfnOutput(
            self, 'ApiURL',
            value=f'https://{self.distribution.distribution_domain_name}/api',
            description='ArchLens API URL'
        )
        
        CfnOutput(
            self, 'S3BucketName',
            value=self.website_bucket.bucket_name,
            description='S3 bucket for frontend deployment'
        )