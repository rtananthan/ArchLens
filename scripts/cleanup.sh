#!/bin/bash

# Cleanup script to destroy all AWS resources
set -e

echo "🧹 Starting ArchLens cleanup..."

# Configuration
ENVIRONMENT=${1:-dev}
AWS_REGION=${2:-us-east-1}

echo "Environment: $ENVIRONMENT"
echo "AWS Region: $AWS_REGION"

# Warning
echo ""
echo "⚠️  WARNING: This will destroy ALL ArchLens AWS resources!"
echo "   This action cannot be undone."
echo ""
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Cleanup cancelled"
    exit 1
fi

# Cleanup S3 buckets first (CDK can't delete non-empty buckets)
echo "🗑️  Emptying S3 buckets..."

# Get bucket names
UPLOAD_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name ArchLens-Storage \
    --query 'Stacks[0].Outputs[?OutputKey==`UploadBucketName`].OutputValue' \
    --output text \
    --region $AWS_REGION 2>/dev/null || echo "")

FRONTEND_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name ArchLens-Frontend \
    --query 'Stacks[0].Outputs[?OutputKey==`S3BucketName`].OutputValue' \
    --output text \
    --region $AWS_REGION 2>/dev/null || echo "")

# Empty buckets
if [ ! -z "$UPLOAD_BUCKET" ]; then
    echo "Emptying upload bucket: $UPLOAD_BUCKET"
    aws s3 rm s3://$UPLOAD_BUCKET --recursive --region $AWS_REGION || true
fi

if [ ! -z "$FRONTEND_BUCKET" ]; then
    echo "Emptying frontend bucket: $FRONTEND_BUCKET"
    aws s3 rm s3://$FRONTEND_BUCKET --recursive --region $AWS_REGION || true
fi

# Destroy CDK stacks
echo "🏗️  Destroying CDK stacks..."
cd infrastructure

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Destroy stacks in reverse order
echo "Destroying Frontend stack..."
cdk destroy ArchLens-Frontend --force --context environment=$ENVIRONMENT || true

echo "Destroying Compute stack..."
cdk destroy ArchLens-Compute --force --context environment=$ENVIRONMENT || true

echo "Destroying AI stack..."
cdk destroy ArchLens-AI --force --context environment=$ENVIRONMENT || true

echo "Destroying Storage stack..."
cdk destroy ArchLens-Storage --force --context environment=$ENVIRONMENT || true

# Deactivate virtual environment
if [ -d "venv" ]; then
    deactivate
fi

cd ..

# Clean up any remaining resources
echo "🧹 Cleaning up remaining resources..."

# Delete any remaining DynamoDB tables
echo "Checking for remaining DynamoDB tables..."
REMAINING_TABLES=$(aws dynamodb list-tables \
    --query 'TableNames[?contains(@, `ArchLens`)]' \
    --output text \
    --region $AWS_REGION)

if [ ! -z "$REMAINING_TABLES" ]; then
    echo "Found remaining tables: $REMAINING_TABLES"
    for table in $REMAINING_TABLES; do
        echo "Deleting table: $table"
        aws dynamodb delete-table --table-name $table --region $AWS_REGION || true
    done
fi

# Delete any remaining Lambda functions
echo "Checking for remaining Lambda functions..."
REMAINING_LAMBDAS=$(aws lambda list-functions \
    --query 'Functions[?contains(FunctionName, `ArchLens`)].FunctionName' \
    --output text \
    --region $AWS_REGION)

if [ ! -z "$REMAINING_LAMBDAS" ]; then
    echo "Found remaining Lambda functions: $REMAINING_LAMBDAS"
    for lambda in $REMAINING_LAMBDAS; do
        echo "Deleting Lambda function: $lambda"
        aws lambda delete-function --function-name $lambda --region $AWS_REGION || true
    done
fi

echo ""
echo "✅ Cleanup completed!"
echo ""
echo "📋 Manual cleanup items (if needed):"
echo "   - Check AWS Console for any remaining resources"
echo "   - Review CloudWatch log groups: /aws/lambda/ArchLens-*"
echo "   - Check IAM roles with 'ArchLens' in the name"
echo "   - Verify no unexpected charges in AWS billing"