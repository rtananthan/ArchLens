#!/bin/bash

# ArchLens Deployment Script
set -e

echo "🚀 Starting ArchLens deployment..."

# Configuration
ENVIRONMENT=${1:-dev}
AWS_REGION=${2:-us-east-1}
CDK_CONTEXT_ENV=${3:-dev}

echo "Environment: $ENVIRONMENT"
echo "AWS Region: $AWS_REGION"
echo "CDK Context: $CDK_CONTEXT_ENV"

# Check prerequisites
echo "📋 Checking prerequisites..."

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured. Please run 'aws configure'."
    exit 1
fi

# Check CDK CLI
if ! command -v cdk &> /dev/null; then
    echo "❌ AWS CDK CLI is not installed. Please install it first:"
    echo "   npm install -g aws-cdk"
    exit 1
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install it first."
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install it first."
    exit 1
fi

echo "✅ Prerequisites check passed"

# Deploy infrastructure
echo "🏗️  Deploying infrastructure..."
cd infrastructure

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing CDK dependencies..."
pip install -r requirements.txt

# Bootstrap CDK (only needed once per account/region)
echo "Bootstrapping CDK..."
cdk bootstrap --context environment=$CDK_CONTEXT_ENV

# Deploy all stacks
echo "Deploying CDK stacks..."
cdk deploy --all --require-approval never --context environment=$CDK_CONTEXT_ENV

# Get stack outputs
echo "📤 Getting stack outputs..."
FRONTEND_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name ArchLens-Frontend \
    --query 'Stacks[0].Outputs[?OutputKey==`S3BucketName`].OutputValue' \
    --output text \
    --region $AWS_REGION)

API_URL=$(aws cloudformation describe-stacks \
    --stack-name ArchLens-Frontend \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiURL`].OutputValue' \
    --output text \
    --region $AWS_REGION)

WEBSITE_URL=$(aws cloudformation describe-stacks \
    --stack-name ArchLens-Frontend \
    --query 'Stacks[0].Outputs[?OutputKey==`WebsiteURL`].OutputValue' \
    --output text \
    --region $AWS_REGION)

echo "Frontend Bucket: $FRONTEND_BUCKET"
echo "API URL: $API_URL"
echo "Website URL: $WEBSITE_URL"

# Deactivate virtual environment
deactivate
cd ..

# Build and deploy frontend
echo "🎨 Building and deploying frontend..."
cd frontend

# Install dependencies
echo "Installing frontend dependencies..."
npm install

# Create environment file
echo "Creating environment configuration..."
cat > .env.local << EOF
NEXT_PUBLIC_API_URL=$API_URL
EOF

# Build the application
echo "Building frontend application..."
npm run build

# Deploy to S3
echo "Deploying to S3..."
aws s3 sync out/ s3://$FRONTEND_BUCKET --delete --region $AWS_REGION

# Invalidate CloudFront cache
echo "Invalidating CloudFront cache..."
DISTRIBUTION_ID=$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?Origins.Items[0].DomainName=='$FRONTEND_BUCKET.s3.amazonaws.com'].Id" \
    --output text \
    --region $AWS_REGION)

if [ ! -z "$DISTRIBUTION_ID" ]; then
    aws cloudfront create-invalidation \
        --distribution-id $DISTRIBUTION_ID \
        --paths "/*" \
        --region $AWS_REGION > /dev/null
    echo "✅ CloudFront cache invalidated"
else
    echo "⚠️  Could not find CloudFront distribution for cache invalidation"
fi

cd ..

echo ""
echo "🎉 Deployment completed successfully!"
echo ""
echo "📱 Application URLs:"
echo "   Website: $WEBSITE_URL"
echo "   API: $API_URL"
echo ""
echo "📋 Next steps:"
echo "   1. Test the application by uploading a draw.io file"
echo "   2. Check CloudWatch logs for any issues"
echo "   3. Monitor costs in the AWS console"
echo ""
echo "🔧 Useful commands:"
echo "   View logs: aws logs tail /aws/lambda/ArchLens-Compute-APILambda --follow"
echo "   Update frontend: ./scripts/deploy-frontend.sh"
echo "   Destroy infrastructure: cd infrastructure && cdk destroy --all"