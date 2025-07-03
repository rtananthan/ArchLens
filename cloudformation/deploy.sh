#!/bin/bash

# ArchLens CloudFormation Deployment Script
# Usage: ./deploy.sh [environment] [region] [lambda-bucket]
# Example: ./deploy.sh prod us-east-1 archlens-deployment-artifacts-123456789012-us-east-1

set -e

# Default values
ENVIRONMENT=${1:-dev}
REGION=${2:-us-east-1}
LAMBDA_BUCKET=${3}
PROJECT_NAME="ArchLens"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validate inputs
if [ -z "$LAMBDA_BUCKET" ]; then
    log_error "Lambda deployment bucket is required"
    echo "Usage: $0 [environment] [region] [lambda-bucket]"
    echo "Example: $0 prod us-east-1 archlens-deployment-artifacts-123456789012-us-east-1"
    exit 1
fi

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    log_error "Environment must be one of: dev, staging, prod"
    exit 1
fi

# Validate region for Bedrock availability
BEDROCK_REGIONS=("us-east-1" "us-west-2" "ap-southeast-2" "eu-west-1")
if [[ ! " ${BEDROCK_REGIONS[@]} " =~ " ${REGION} " ]]; then
    log_warning "Region $REGION may not support Amazon Bedrock"
    log_warning "Supported regions: ${BEDROCK_REGIONS[*]}"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

log_info "Deploying ArchLens to environment: $ENVIRONMENT, region: $REGION"

# Check AWS CLI and credentials
if ! command -v aws &> /dev/null; then
    log_error "AWS CLI is not installed"
    exit 1
fi

if ! aws sts get-caller-identity &> /dev/null; then
    log_error "AWS credentials not configured or invalid"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
log_info "Deploying to AWS Account: $ACCOUNT_ID"

# Check if Lambda bucket exists
if ! aws s3 ls "s3://$LAMBDA_BUCKET" &> /dev/null; then
    log_error "Lambda deployment bucket s3://$LAMBDA_BUCKET does not exist"
    log_info "Create it with: aws s3 mb s3://$LAMBDA_BUCKET"
    exit 1
fi

# Package and upload Lambda code if backend_clean directory exists
if [ -d "../backend_clean" ]; then
    log_info "Packaging Lambda code..."
    cd ../backend_clean
    
    # Create deployment package
    if [ -f "../archlens-backend.zip" ]; then
        rm ../archlens-backend.zip
    fi
    
    zip -r ../archlens-backend.zip . -x "*.pyc" "__pycache__/*" "tests/*" "*.git*"
    
    # Upload to S3
    log_info "Uploading Lambda package to S3..."
    aws s3 cp ../archlens-backend.zip "s3://$LAMBDA_BUCKET/lambda/archlens-backend.zip"
    
    cd ../cloudformation
    log_success "Lambda package uploaded successfully"
else
    log_warning "Backend code directory not found, assuming Lambda package already uploaded"
fi

# Function to check stack status
check_stack_status() {
    local stack_name=$1
    local status
    
    status=$(aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "NOT_EXISTS")
    
    echo "$status"
}

# Function to wait for stack completion
wait_for_stack() {
    local stack_name=$1
    local operation=$2
    
    log_info "Waiting for stack $stack_name to complete $operation..."
    
    aws cloudformation wait "stack-${operation}-complete" --stack-name "$stack_name" || {
        log_error "Stack $stack_name $operation failed"
        aws cloudformation describe-stack-events --stack-name "$stack_name" \
            --query 'StackEvents[?ResourceStatusReason!=`null`].[Timestamp,ResourceStatus,ResourceStatusReason]' \
            --output table
        return 1
    }
    
    log_success "Stack $stack_name $operation completed successfully"
}

# Function to deploy stack
deploy_stack() {
    local stack_name=$1
    local template_file=$2
    local parameters=$3
    local capabilities=$4
    
    local status
    status=$(check_stack_status "$stack_name")
    
    local operation="create"
    if [ "$status" != "NOT_EXISTS" ]; then
        operation="update"
    fi
    
    log_info "$(echo "$operation" | tr '[:lower:]' '[:upper:]')ing stack: $stack_name"
    
    local cmd="aws cloudformation ${operation}-stack \
        --region $REGION \
        --stack-name $stack_name \
        --template-body file://$template_file"
    
    if [ -n "$parameters" ]; then
        cmd="$cmd --parameters $parameters"
    fi
    
    if [ -n "$capabilities" ]; then
        cmd="$cmd --capabilities $capabilities"
    fi
    
    # Add tags
    cmd="$cmd --tags Key=Project,Value=$PROJECT_NAME Key=Environment,Value=$ENVIRONMENT Key=DeployedBy,Value=$(whoami) Key=DeployedAt,Value=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    
    eval "$cmd" || {
        if [ "$operation" == "update" ]; then
            log_warning "Update may have failed due to no changes"
            return 0
        else
            log_error "Failed to $operation stack $stack_name"
            return 1
        fi
    }
    
    wait_for_stack "$stack_name" "$operation"
}

# Deploy stacks in order
log_info "Starting deployment of all stacks..."

# 1. Storage Stack
deploy_stack \
    "$PROJECT_NAME-Storage-$ENVIRONMENT" \
    "01-storage.yaml" \
    "ParameterKey=Environment,ParameterValue=$ENVIRONMENT ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME"

# 2. AI Stack  
deploy_stack \
    "$PROJECT_NAME-AI-$ENVIRONMENT" \
    "02-ai.yaml" \
    "ParameterKey=Environment,ParameterValue=$ENVIRONMENT ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME" \
    "CAPABILITY_NAMED_IAM"

# 3. Compute Stack
deploy_stack \
    "$PROJECT_NAME-Compute-$ENVIRONMENT" \
    "03-compute.yaml" \
    "ParameterKey=Environment,ParameterValue=$ENVIRONMENT ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME ParameterKey=LambdaCodeBucket,ParameterValue=$LAMBDA_BUCKET" \
    "CAPABILITY_NAMED_IAM"

# 4. Frontend Stack
deploy_stack \
    "$PROJECT_NAME-Frontend-$ENVIRONMENT" \
    "04-frontend.yaml" \
    "ParameterKey=Environment,ParameterValue=$ENVIRONMENT ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME" \
    "CAPABILITY_IAM"

# Get deployment outputs
log_info "Retrieving deployment outputs..."

API_URL=$(aws cloudformation describe-stacks \
    --stack-name "$PROJECT_NAME-Compute-$ENVIRONMENT" \
    --query 'Stacks[0].Outputs[?OutputKey==`APIGatewayURL`].OutputValue' \
    --output text 2>/dev/null || echo "Not found")

FRONTEND_URL=$(aws cloudformation describe-stacks \
    --stack-name "$PROJECT_NAME-Frontend-$ENVIRONMENT" \
    --query 'Stacks[0].Outputs[?OutputKey==`WebsiteURL`].OutputValue' \
    --output text 2>/dev/null || echo "Not found")

FRONTEND_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name "$PROJECT_NAME-Frontend-$ENVIRONMENT" \
    --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' \
    --output text 2>/dev/null || echo "Not found")

# Display deployment summary
echo
log_success "🎉 ArchLens deployment completed successfully!"
echo
echo "📋 Deployment Summary:"
echo "======================"
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo "Account: $ACCOUNT_ID"
echo
echo "🔗 Application URLs:"
echo "Frontend: $FRONTEND_URL"
echo "API: $API_URL"
echo
echo "📦 Resources Created:"
echo "Frontend Bucket: $FRONTEND_BUCKET"
echo
echo "🚀 Next Steps:"
echo "1. Deploy frontend code:"
echo "   cd ../frontend && npm run build"
echo "   aws s3 sync out/ s3://$FRONTEND_BUCKET --delete"
echo
echo "2. Test the API:"
echo "   curl $API_URL/api/health"
echo
echo "3. Access the application:"
echo "   open $FRONTEND_URL"
echo

# Check for Bedrock quotas
log_info "Checking Bedrock quotas..."
CLAUDE_QUOTA=$(aws service-quotas get-service-quota \
    --service-code bedrock \
    --quota-code L-254CACF4 \
    --query 'Quota.Value' \
    --output text 2>/dev/null || echo "unknown")

if [ "$CLAUDE_QUOTA" == "1.0" ] || [ "$CLAUDE_QUOTA" == "1" ]; then
    echo
    log_warning "⚠️  IMPORTANT: Bedrock quota limitation detected"
    echo "Claude 3.5 Sonnet quota: $CLAUDE_QUOTA requests/minute"
    echo
    echo "🎫 Create AWS Support case to increase quotas:"
    echo "   - Go to AWS Console → Support → Create case"
    echo "   - Choose 'Service limit increase'"
    echo "   - Request 100 requests/minute for production usage"
    echo "   - Reference quota code: L-254CACF4"
    echo
fi

echo "✅ Deployment completed at $(date)"