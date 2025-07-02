# ArchLens Deployment Guide

This guide provides detailed instructions for deploying ArchLens to AWS, including troubleshooting common issues and optimizing the deployment for production use.

## 🎯 Prerequisites Checklist

### AWS Account Setup
- [ ] AWS account with administrative permissions
- [ ] AWS CLI installed and configured (`aws configure`)
- [ ] AWS CDK CLI installed (`npm install -g aws-cdk`)
- [ ] CDK bootstrapped in your region (`cdk bootstrap`)

### Development Environment
- [ ] Python 3.11+ installed
- [ ] Node.js 18+ and npm installed
- [ ] Git installed

### AWS Permissions Required
Your AWS user/role needs the following permissions:
- CloudFormation (full access)
- IAM (create/update roles and policies)
- Lambda (full access)
- API Gateway (full access)
- S3 (full access)
- DynamoDB (full access)
- CloudFront (full access)
- Bedrock (agent creation and invocation)

## 🚀 Step-by-Step Deployment

### Step 1: Repository Setup

```bash
# Clone the repository
git clone <your-repository-url>
cd ArchLens

# Verify project structure
ls -la
# Should see: frontend/, backend_clean/, infrastructure/, docs/, examples/
```

### Step 2: Infrastructure Dependencies

```bash
cd infrastructure

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install CDK dependencies
pip install -r requirements.txt

# Verify CDK installation
cdk --version
# Should show CDK version 2.x
```

### Step 3: Bootstrap CDK (One-time setup)

```bash
# Bootstrap CDK in your region
cdk bootstrap

# Expected output:
# ✅  Environment aws://123456789012/us-east-1 bootstrapped
```

### Step 4: Deploy Infrastructure Stacks

```bash
# Deploy all stacks (recommended order)
cdk deploy --all --require-approval never

# Alternative: Deploy stacks individually
cdk deploy ArchLens-Storage --require-approval never
cdk deploy ArchLens-AI --require-approval never
cdk deploy ArchLens-Compute --require-approval never
cdk deploy ArchLens-Frontend --require-approval never
```

**Expected Deployment Time:**
- Storage Stack: ~2 minutes
- AI Stack: ~3-5 minutes
- Compute Stack: ~3-4 minutes
- Frontend Stack: ~8-10 minutes (CloudFront distribution)

### Step 5: Configure Frontend

```bash
cd ../frontend

# Install dependencies
npm install

# Update API endpoint (if needed)
# Edit lib/api.ts with your API Gateway URL from CDK output
```

### Step 6: Build and Deploy Frontend

```bash
# Build for production
npm run build

# Get your frontend bucket name from CDK output
# Should be something like: archlens-frontend-bucket-123456-region

# Deploy to S3
aws s3 sync out/ s3://your-frontend-bucket-name --delete

# Invalidate CloudFront cache (optional but recommended)
aws cloudfront create-invalidation \
  --distribution-id YOUR_DISTRIBUTION_ID \
  --paths "/*"
```

### Step 7: Verify Deployment

```bash
# Test API health endpoint
curl https://your-api-gateway-url/api/health

# Should return:
# {
#   "status": "healthy",
#   "message": "ArchLens API with real Bedrock integration",
#   "version": "2.0.0"
# }
```

## 🔧 Configuration Details

### Environment Variables (Auto-configured by CDK)

| Variable | Example Value | Description |
|----------|---------------|-------------|
| `UPLOAD_BUCKET` | `archlens-uploads-123456-ap-southeast-2` | S3 bucket for uploaded files |
| `ANALYSIS_TABLE` | `ArchLens-Analysis-ap-southeast-2` | DynamoDB table for results |
| `BEDROCK_AGENT_ID` | `BQ2AJX1QNF` | Auto-generated Bedrock agent ID |
| `BEDROCK_AGENT_ALIAS_ID` | `TSTALIASID` | Default test alias |
| `AWS_REGION` | `ap-southeast-2` | Deployment region |

### Resource Naming Convention

All resources follow this pattern: `archlens-{service}-{account}-{region}`

Examples:
- S3 Upload Bucket: `archlens-uploads-123456789012-ap-southeast-2`
- S3 Frontend Bucket: `archlens-frontend-bucket-123456789012-ap-southeast-2`
- DynamoDB Table: `ArchLens-Analysis-ap-southeast-2`
- Lambda Function: `ArchLens-Compute-APILambda7D19CDDA-randomstring`

## 🛠️ Troubleshooting Common Issues

### Issue 1: CDK Bootstrap Failed

**Error:** `This stack uses assets, so the toolkit stack must be deployed`

**Solution:**
```bash
# Ensure you're in the right region
aws configure get region

# Bootstrap with explicit region
cdk bootstrap aws://ACCOUNT-ID/REGION

# Example:
cdk bootstrap aws://123456789012/ap-southeast-2
```

### Issue 2: Bedrock Not Available in Region

**Error:** `Bedrock services are not available in this region`

**Supported Regions for Bedrock:**
- `us-east-1` (N. Virginia)
- `us-west-2` (Oregon)
- `ap-southeast-2` (Sydney)
- `eu-west-1` (Ireland)

**Solution:** Deploy to a supported region or use cross-region Bedrock calls.

### Issue 3: Bedrock Agent Creation Failed

**Error:** `User is not authorized to perform: bedrock:CreateAgent`

**Solution:**
```bash
# Check Bedrock permissions
aws iam list-attached-user-policies --user-name YOUR_USERNAME

# Required policies:
# - AmazonBedrockFullAccess
# - IAMFullAccess (for agent role creation)
```

### Issue 4: Lambda Timeout During Deployment

**Error:** `The following resource(s) failed to create: [APILambda]`

**Solution:**
```bash
# Check Lambda size limits
ls -la backend_clean/

# If deployment package is too large, use lightweight handlers:
cd infrastructure
cdk deploy ArchLens-Compute --require-approval never
```

### Issue 5: Frontend Not Loading

**Symptoms:** 
- CloudFront URL returns 404
- Static assets not loading

**Solution:**
```bash
# 1. Verify S3 sync completed
aws s3 ls s3://your-frontend-bucket-name/

# 2. Check CloudFront distribution
aws cloudfront list-distributions

# 3. Re-sync with proper permissions
aws s3 sync frontend/out/ s3://your-frontend-bucket-name \
  --delete --acl public-read

# 4. Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id YOUR_DIST_ID \
  --paths "/*"
```

### Issue 6: API Gateway CORS Errors

**Error:** `Access to fetch at 'https://api...' from origin 'https://cloudfront...' has been blocked by CORS policy`

**Solution:**
The CDK automatically configures CORS, but if issues persist:

```bash
# Redeploy compute stack
cd infrastructure
cdk deploy ArchLens-Compute --require-approval never

# Verify CORS configuration in AWS Console:
# API Gateway → Your API → Resources → Actions → Enable CORS
```

## 🎯 Production Optimization

### Security Hardening

1. **Enable AWS CloudTrail**
```bash
aws cloudtrail create-trail \
  --name ArchLens-Audit-Trail \
  --s3-bucket-name your-cloudtrail-bucket
```

2. **Set up CloudWatch Alarms**
```bash
# Example: Monitor Lambda errors
aws cloudwatch put-metric-alarm \
  --alarm-name "ArchLens-Lambda-Errors" \
  --alarm-description "Monitor Lambda function errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold
```

3. **Enable S3 Bucket Versioning**
```bash
aws s3api put-bucket-versioning \
  --bucket your-upload-bucket \
  --versioning-configuration Status=Enabled
```

### Performance Optimization

1. **Lambda Reserved Concurrency**
```python
# Add to compute_stack.py
self.api_lambda.add_property_override(
    "ReservedConcurrencyConfiguration", {
        "ReservedConcurrency": 10
    }
)
```

2. **DynamoDB Auto Scaling**
```python
# Add to storage_stack.py
self.analysis_table.auto_scale_read_capacity(
    min_capacity=5,
    max_capacity=100
).scale_on_utilization(target_utilization_percent=70)
```

3. **CloudFront Caching**
- Default: Already optimized for static assets
- API Gateway: Consider adding caching for GET endpoints

### Cost Optimization

1. **S3 Lifecycle Policies**
```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket your-upload-bucket \
  --lifecycle-configuration file://lifecycle.json
```

2. **DynamoDB TTL**
- Already configured (7 days auto-expiry)
- Adjust in `storage_stack.py` if needed

3. **Lambda Memory Optimization**
- Monitor CloudWatch metrics
- Adjust memory allocation based on actual usage

## 📊 Monitoring and Observability

### CloudWatch Dashboards

Create a custom dashboard to monitor:
- Lambda invocation count and duration
- API Gateway request count and latency
- DynamoDB read/write capacity
- S3 storage metrics
- Bedrock API usage

### Log Analysis

```bash
# Real-time log monitoring
aws logs tail /aws/lambda/ArchLens-Compute-APILambda --follow

# Search for specific patterns
aws logs filter-log-events \
  --log-group-name "/aws/lambda/ArchLens-Compute-APILambda" \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s)000
```

### Health Checks

Set up automated health checks:

```bash
#!/bin/bash
# health-check.sh
API_URL="https://your-api-gateway-url"

# Test health endpoint
response=$(curl -s "$API_URL/api/health")
if [[ $response == *"healthy"* ]]; then
    echo "✅ API is healthy"
else
    echo "❌ API health check failed"
    exit 1
fi

# Test file upload
response=$(curl -s -X POST "$API_URL/api/analyze" \
  -F "file=@examples/sample-aws-architecture.xml")
if [[ $response == *"analysis_id"* ]]; then
    echo "✅ File upload working"
else
    echo "❌ File upload failed"
    exit 1
fi
```

## 🔄 Updates and Maintenance

### Updating the Application

1. **Update Infrastructure**
```bash
cd infrastructure
source venv/bin/activate
cdk deploy ArchLens-Compute --require-approval never
```

2. **Update Frontend**
```bash
cd frontend
npm run build
aws s3 sync out/ s3://your-frontend-bucket --delete
aws cloudfront create-invalidation --distribution-id YOUR_ID --paths "/*"
```

3. **Rolling Updates**
- Lambda functions update automatically
- API Gateway changes require redeployment
- CloudFront changes may take 15-20 minutes to propagate

### Backup Strategy

1. **DynamoDB Backups**
```bash
# Enable point-in-time recovery
aws dynamodb update-continuous-backups \
  --table-name ArchLens-Analysis-ap-southeast-2 \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true
```

2. **S3 Cross-Region Replication**
```bash
# Set up replication for critical data
aws s3api put-bucket-replication \
  --bucket your-upload-bucket \
  --replication-configuration file://replication.json
```

## 🌍 Multi-Region Deployment

For global applications, consider deploying to multiple regions:

1. **Primary Region**: Full deployment
2. **Secondary Regions**: Frontend + API Gateway only
3. **Cross-Region**: DynamoDB Global Tables for data replication

```bash
# Deploy to multiple regions
export AWS_DEFAULT_REGION=us-east-1
cdk deploy --all

export AWS_DEFAULT_REGION=eu-west-1
cdk deploy --all
```

## 📞 Support and Troubleshooting

### Getting Help

1. **Check CloudWatch Logs**: Always start with Lambda and API Gateway logs
2. **AWS Support**: For infrastructure issues
3. **GitHub Issues**: For application-specific problems
4. **AWS Documentation**: For service-specific guidance

### Emergency Recovery

If the deployment fails completely:

```bash
# 1. Destroy and recreate
cd infrastructure
cdk destroy --all

# 2. Clean up any remaining resources manually
# 3. Bootstrap and redeploy
cdk bootstrap
cdk deploy --all --require-approval never
```

### Contact Information

- **Issues**: Create GitHub issue with deployment logs
- **Feature Requests**: Use GitHub Discussions
- **Security Issues**: Email security@yourcompany.com

---

**Remember**: Always test deployments in a development environment before deploying to production!