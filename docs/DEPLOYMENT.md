# ArchLens Deployment Guide

This guide covers how to deploy ArchLens to AWS and set up local development.

## Prerequisites

### Required Tools
- **AWS CLI**: Configured with appropriate credentials
- **AWS CDK CLI**: `npm install -g aws-cdk`
- **Node.js**: Version 18 or higher
- **Python**: Version 3.11 or higher
- **Git**: For cloning the repository

### AWS Account Requirements
- AWS account with administrative access
- AWS CLI configured with credentials
- Sufficient service limits for:
  - Lambda functions
  - S3 buckets
  - DynamoDB tables
  - CloudFront distributions
  - API Gateway APIs

## Quick Deployment

### 1. Clone and Setup
```bash
git clone <repository-url>
cd ArchLens
chmod +x scripts/*.sh
```

### 2. Deploy Everything
```bash
./scripts/deploy.sh
```

This script will:
- Check prerequisites
- Deploy CDK infrastructure
- Build and deploy the frontend
- Provide you with the application URLs

### 3. Access Your Application
After deployment, you'll get:
- **Website URL**: Your main application
- **API URL**: Direct API access (for testing)

## Manual Deployment Steps

If you prefer to deploy step by step:

### 1. Infrastructure Deployment

```bash
cd infrastructure

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install CDK dependencies
pip install -r requirements.txt

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy all stacks
cdk deploy --all
```

### 2. Frontend Deployment

```bash
cd frontend

# Install dependencies
npm install

# Set API URL (get from CDK outputs)
echo "NEXT_PUBLIC_API_URL=https://your-api-url" > .env.local

# Build and deploy
npm run build

# Upload to S3 (get bucket name from CDK outputs)
aws s3 sync out/ s3://your-frontend-bucket --delete
```

## Environment Configuration

### Production Environment
For production deployment:

```bash
# Deploy with production context
./scripts/deploy.sh prod us-east-1 prod
```

### Development Environment
For development/testing:

```bash
# Deploy with dev context (default)
./scripts/deploy.sh dev us-east-1 dev
```

## Local Development Setup

### 1. Setup Local Environment
```bash
./scripts/local-dev.sh
```

### 2. Run Backend Locally
```bash
cd backend
source venv/bin/activate
uvicorn src.handlers.api:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Run Frontend Locally
```bash
cd frontend
npm run dev
```

### 4. Access Local Application
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

## Configuration Options

### Environment Variables

#### Backend (.env)
```bash
UPLOAD_BUCKET=your-upload-bucket
ANALYSIS_TABLE=your-analysis-table
BEDROCK_AGENT_ID=your-bedrock-agent-id
BEDROCK_AGENT_ALIAS_ID=TSTALIASID
AWS_REGION=us-east-1
```

#### Frontend (.env.local)
```bash
NEXT_PUBLIC_API_URL=https://your-api-gateway-url
```

### CDK Context Variables
Configure in `infrastructure/cdk.json`:

```json
{
  "context": {
    "environment": "dev|staging|prod",
    "@aws-cdk/core:enableStackNameDuplicates": true
  }
}
```

## Monitoring and Troubleshooting

### View Logs
```bash
# API Lambda logs
aws logs tail /aws/lambda/ArchLens-Compute-APILambda --follow

# Processor Lambda logs  
aws logs tail /aws/lambda/ArchLens-Compute-ProcessorLambda --follow
```

### Check Stack Status
```bash
aws cloudformation describe-stacks --stack-name ArchLens-Storage
aws cloudformation describe-stacks --stack-name ArchLens-Compute
aws cloudformation describe-stacks --stack-name ArchLens-AI
aws cloudformation describe-stacks --stack-name ArchLens-Frontend
```

### Health Check
```bash
# Test API health endpoint
curl https://your-api-url/api/health
```

## Cost Optimization

### Estimated Monthly Costs (Light Usage)
- **S3 Storage**: $5-10 (depending on file storage)
- **Lambda**: $5-15 (based on analysis volume)
- **DynamoDB**: $2-5 (on-demand pricing)
- **CloudFront**: $1-5 (data transfer)
- **API Gateway**: $1-3 (API calls)
- **Bedrock**: $10-50 (AI analysis calls)

**Total**: ~$25-90/month for light usage

### Cost Controls
1. **S3 Lifecycle**: Files auto-delete after 48 hours
2. **Lambda Timeout**: Set to 15 minutes max
3. **DynamoDB TTL**: Records auto-expire
4. **CloudFront**: Optimized caching rules

## Security Considerations

### Implemented Security
- ✅ S3 buckets with restricted access
- ✅ IAM roles with least privilege
- ✅ API Gateway throttling
- ✅ HTTPS everywhere
- ✅ Resource tagging

### Additional Security (Recommended)
- 🔄 Add WAF to API Gateway
- 🔄 Implement Cognito authentication
- 🔄 Add CloudTrail logging
- 🔄 Set up GuardDuty monitoring

## Backup and Recovery

### Automated Backups
- **DynamoDB**: Point-in-time recovery enabled
- **S3**: Versioning disabled (cost optimization)
- **Lambda**: Code stored in CDK/Git

### Manual Backup
```bash
# Export DynamoDB table
aws dynamodb scan --table-name ArchLens-Analysis > backup.json

# Backup S3 bucket
aws s3 sync s3://your-bucket/ ./s3-backup/
```

## Cleanup and Teardown

### Quick Cleanup
```bash
./scripts/cleanup.sh
```

### Manual Cleanup
```bash
cd infrastructure
cdk destroy --all
```

### Cost Verification
After cleanup, verify in AWS Console:
- Check billing dashboard
- Ensure all resources are deleted
- Review any remaining charges

## Troubleshooting Common Issues

### CDK Bootstrap Issues
```bash
# If bootstrap fails
cdk bootstrap --trust=ACCOUNT-ID --cloudformation-execution-policies arn:aws:iam::aws:policy/AdministratorAccess
```

### Lambda Deployment Issues
```bash
# Check Lambda package size
cd backend && zip -r lambda.zip . && ls -lh lambda.zip

# Verify Python dependencies
pip list
```

### Frontend Build Issues
```bash
# Clear Next.js cache
cd frontend && rm -rf .next out node_modules && npm install
```

### Permission Issues
```bash
# Check AWS credentials
aws sts get-caller-identity

# Verify IAM permissions
aws iam get-user
```

## Support and Updates

### Getting Help
1. Check CloudWatch logs first
2. Review CDK outputs for resource names
3. Verify environment variables
4. Test API endpoints directly

### Updates and Maintenance
```bash
# Update CDK stacks
cd infrastructure && cdk diff && cdk deploy --all

# Update frontend only
./scripts/deploy-frontend.sh

# Update dependencies
cd backend && pip install -r requirements.txt --upgrade
cd frontend && npm update
```