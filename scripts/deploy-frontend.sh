#!/bin/bash

# Frontend-only deployment script
set -e

echo "🎨 Deploying frontend only..."

# Configuration
AWS_REGION=${1:-us-east-1}

# Get S3 bucket name from CloudFormation
FRONTEND_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name ArchLens-Frontend \
    --query 'Stacks[0].Outputs[?OutputKey==`S3BucketName`].OutputValue' \
    --output text \
    --region $AWS_REGION)

if [ -z "$FRONTEND_BUCKET" ]; then
    echo "❌ Could not find frontend S3 bucket. Make sure infrastructure is deployed."
    exit 1
fi

echo "Frontend Bucket: $FRONTEND_BUCKET"

# Build and deploy frontend
cd frontend

echo "Installing dependencies..."
npm install

echo "Building application..."
npm run build

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
fi

cd ..

echo "✅ Frontend deployment completed!"