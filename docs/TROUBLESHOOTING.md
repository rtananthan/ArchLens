# ArchLens Troubleshooting Guide

This guide covers common issues you might encounter when deploying and using ArchLens, with specific focus on Bedrock quota limitations and permission issues.

## 🚨 Critical Issues

### 1. Bedrock Quota Limitations (Most Common)

#### Symptoms
- Error: `⚠️ Bedrock Quota Limit: Your account has a 1 request/minute quota`
- Analysis returns: "AI service temporarily unavailable"
- Response: `throttlingException: Your request rate is too high`

#### Root Cause
AWS has dramatically reduced Bedrock quotas for new accounts (as of October 2024):
- **Claude 3.5 Sonnet**: Only 1 request/minute (default)
- **Claude 3.7 Sonnet**: Only 4 requests/minute (default)

#### Immediate Solutions

**Option 1: Request Quota Increase (Recommended)**
```bash
# 1. Go to AWS Console → Service Quotas
# 2. Search for "Bedrock"
# 3. Find "On-demand model inference requests per minute for Anthropic Claude 3.5 Sonnet"
# 4. Click "Request quota increase"
# 5. Request increase to 50-100 requests/minute
# 6. Business justification: "Production architecture analysis SaaS application"
```

**Option 2: Wait Between Requests**
```bash
# For testing, wait 60+ seconds between API calls
sleep 60
curl -X POST https://your-api-url/api/analyze -F "file=@test.drawio"
```

**Option 3: Check Current Quotas**
```bash
# List current Bedrock quotas
aws service-quotas list-service-quotas --service-code bedrock \
  --query 'Quotas[?contains(QuotaName, `Claude`)]' \
  --output table
```

#### Cost Impact of Quota Increase
- **Quota increase is FREE** - you only pay for actual usage
- Each analysis costs ~$0.008 USD (less than 1 cent)
- 100 requests/minute quota enables production usage without forced costs

### 2. Bedrock Permission Issues

#### Symptoms
- Error: `🔒 Permission Error: Insufficient Bedrock permissions`
- CloudWatch logs: `AccessDeniedException: User is not authorized to perform: bedrock:InvokeAgent`

#### Solution
```bash
# 1. Check Lambda execution role permissions
aws iam get-role-policy \
  --role-name "ArchLens-Compute-LambdaExecutionRole*" \
  --policy-name "ArchLensLambdaPolicy"

# 2. Verify Bedrock permissions include:
# - bedrock:InvokeAgent
# - bedrock-agent-runtime:InvokeAgent  
# - bedrock-runtime:InvokeModel

# 3. Redeploy compute stack if permissions are missing
cd infrastructure
source venv/bin/activate
cdk deploy ArchLens-Compute --require-approval never
```

### 3. Bedrock Service Not Available

#### Symptoms
- Error: `Bedrock services are not available in this region`
- Agent creation fails during AI stack deployment

#### Supported Regions
✅ **Fully Supported:**
- `us-east-1` (N. Virginia)
- `us-west-2` (Oregon)  
- `ap-southeast-2` (Sydney)
- `eu-west-1` (Ireland)

❌ **Limited/No Support:**
- `us-east-2`, `ap-southeast-1`, `eu-central-1`, etc.

#### Solution
```bash
# Deploy to a supported region
export AWS_DEFAULT_REGION=ap-southeast-2
cd infrastructure
cdk deploy --all --require-approval never
```

## 🔧 Deployment Issues

### CDK Bootstrap Issues

#### Problem: Stack uses assets but toolkit not deployed
```bash
# Error: This stack uses assets, so the toolkit stack must be deployed to the environment
```

#### Solution
```bash
# Bootstrap with explicit account and region
cdk bootstrap aws://123456789012/ap-southeast-2

# If bootstrap fails, check permissions
aws sts get-caller-identity
aws iam list-attached-user-policies --user-name $(aws sts get-caller-identity --query 'Arn' --output text | cut -d'/' -f2)
```

### Lambda Deployment Failures

#### Problem: Function code too large
```bash
# Error: Function code combined with layers exceeds maximum size
```

#### Solution
```bash
# Use lightweight handlers (already implemented)
cd infrastructure
cdk deploy ArchLens-Compute --require-approval never

# Verify handler size
ls -la backend_clean/
# Should show lightweight_handler.py (~30KB)
```

#### Problem: Lambda timeout during deployment
```bash
# Error: The following resource(s) failed to create: [APILambda]
```

#### Solution
```bash
# Check CloudFormation events for details
aws cloudformation describe-stack-events --stack-name ArchLens-Compute

# Common fixes:
# 1. Retry deployment
cdk deploy ArchLens-Compute --require-approval never

# 2. If still failing, destroy and recreate
cdk destroy ArchLens-Compute
cdk deploy ArchLens-Compute --require-approval never
```

## 🌐 API and Frontend Issues

### CORS Errors

#### Symptoms
```javascript
// Browser console error:
Access to fetch at 'https://api...' from origin 'https://cloudfront...' 
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header
```

#### Solution
```bash
# 1. Verify API Gateway CORS configuration
aws apigateway get-resources --rest-api-id YOUR_API_ID

# 2. Redeploy compute stack (fixes CORS)
cd infrastructure
cdk deploy ArchLens-Compute --require-approval never

# 3. Test CORS manually
curl -H "Origin: https://your-cloudfront-domain" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: Content-Type" \
     -X OPTIONS \
     https://your-api-gateway-url/api/analyze
```

### Frontend Not Loading

#### Problem: CloudFront returns 404 for all routes
```bash
# Error: The specified key does not exist
```

#### Solution
```bash
# 1. Verify S3 bucket contents
aws s3 ls s3://your-frontend-bucket-name/

# 2. Re-sync frontend with correct permissions
cd frontend
npm run build
aws s3 sync out/ s3://your-frontend-bucket-name --delete

# 3. Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id YOUR_DISTRIBUTION_ID \
  --paths "/*"

# 4. Check CloudFront distribution status
aws cloudfront get-distribution --id YOUR_DISTRIBUTION_ID \
  --query 'Distribution.Status'
# Should be "Deployed"
```

### API Gateway 504 Timeout

#### Symptoms
- Requests timeout after 29 seconds
- Error: `{"message": "Endpoint request timed out"}`

#### Root Cause
API Gateway has a 29-second timeout limit, but Bedrock analysis with retries can take longer.

#### Solution
```bash
# Check Lambda timeout settings
aws lambda get-function-configuration \
  --function-name ArchLens-Compute-APILambda* \
  --query 'Timeout'

# Lambda timeout should be < 29 seconds for synchronous calls
# Current setting: 15 minutes (900 seconds) - needs adjustment for sync calls

# For immediate fix, reduce retry delays in handler
# Already implemented: base_delay = 10 seconds, max_retries = 1
```

## 📊 Monitoring and Debugging

### CloudWatch Logs Analysis

#### View Real-time Logs
```bash
# Follow Lambda logs in real-time
aws logs tail /aws/lambda/ArchLens-Compute-APILambda --follow

# View recent errors only
aws logs filter-log-events \
  --log-group-name "/aws/lambda/ArchLens-Compute-APILambda" \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s)000
```

#### Common Log Patterns to Search For

**Bedrock Throttling:**
```bash
aws logs filter-log-events \
  --log-group-name "/aws/lambda/ArchLens-Compute-APILambda" \
  --filter-pattern "throttling"
```

**Permission Errors:**
```bash
aws logs filter-log-events \
  --log-group-name "/aws/lambda/ArchLens-Compute-APILambda" \
  --filter-pattern "AccessDeniedException"
```

**File Upload Issues:**
```bash
aws logs filter-log-events \
  --log-group-name "/aws/lambda/ArchLens-Compute-APILambda" \
  --filter-pattern "File.*Error"
```

### Health Check Script

Create a comprehensive health check:

```bash
#!/bin/bash
# health-check.sh
set -e

API_URL="https://your-api-gateway-url"
echo "🔍 Testing ArchLens Health..."

# 1. Test API health endpoint
echo "Testing /api/health..."
response=$(curl -s "$API_URL/api/health")
if [[ $response == *"healthy"* ]]; then
    echo "✅ API health check passed"
else
    echo "❌ API health check failed: $response"
    exit 1
fi

# 2. Test file upload with small file
echo "Testing file upload..."
echo '<?xml version="1.0"?><mxfile><diagram><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/></root></mxGraphModel></diagram></mxfile>' > /tmp/test.drawio

response=$(curl -s -X POST "$API_URL/api/analyze" -F "file=@/tmp/test.drawio")
if [[ $response == *"analysis_id"* ]]; then
    echo "✅ File upload working"
    
    # Extract analysis_id and test result retrieval
    analysis_id=$(echo $response | jq -r '.analysis_id')
    echo "Testing analysis retrieval for $analysis_id..."
    
    sleep 5  # Wait for processing
    result=$(curl -s "$API_URL/api/analysis/$analysis_id")
    if [[ $result == *"results"* ]]; then
        echo "✅ Analysis retrieval working"
    else
        echo "⚠️  Analysis retrieval returned: $result"
    fi
else
    echo "❌ File upload failed: $response"
    
    # Check if it's a quota issue
    if [[ $response == *"quota"* ]] || [[ $response == *"throttling"* ]]; then
        echo "💡 This appears to be a Bedrock quota limitation"
        echo "   Solution: Request quota increase in AWS Console → Service Quotas"
    fi
fi

rm -f /tmp/test.drawio
echo "🏁 Health check completed"
```

## 🔐 Security Issues

### S3 Bucket Access Denied

#### Problem
```bash
# Error: Access Denied when uploading to S3
aws s3 cp test.txt s3://your-bucket/
# upload failed: Unable to locate credentials
```

#### Solution
```bash
# 1. Check AWS credentials
aws sts get-caller-identity

# 2. Verify bucket policy allows your operations
aws s3api get-bucket-policy --bucket your-bucket-name

# 3. Check if bucket exists in correct region
aws s3api get-bucket-location --bucket your-bucket-name
```

### DynamoDB Access Issues

#### Problem
```bash
# Error: User is not authorized to perform: dynamodb:PutItem
```

#### Solution
```bash
# Check DynamoDB permissions in Lambda execution role
aws iam get-role-policy \
  --role-name "ArchLens-Compute-LambdaExecutionRole*" \
  --policy-name "ArchLensLambdaPolicy" \
  --query 'PolicyDocument.Statement[?contains(Action, `dynamodb`)]'
```

## 💾 Data Issues

### DynamoDB Decimal Errors

#### Problem
```python
# Error: Float types are not supported. Use Decimal types instead
TypeError: Float types are not supported. Use Decimal types instead
```

#### Solution
Already implemented in `lightweight_handler.py`:
```python
def convert_floats_to_decimal(obj):
    if isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(v) for v in obj]
    elif isinstance(obj, float):
        return Decimal(str(obj))
    else:
        return obj
```

### File Upload Parsing Errors

#### Problem
```bash
# Error: Unable to parse the uploaded file. Please try again with a valid draw.io file
```

#### Debug Steps
```bash
# 1. Verify file format
file your-file.drawio
# Should show: XML document text

# 2. Check XML validity
xmllint --noout your-file.drawio
# Should show no errors

# 3. Verify content
head -n 10 your-file.drawio
# Should start with: <?xml version="1.0"
```

## 🚀 Performance Issues

### Slow Response Times

#### Problem: API responses taking > 10 seconds

#### Analysis
```bash
# Check Lambda duration metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=ArchLens-Compute-APILambda* \
  --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum
```

#### Solutions
1. **Increase Lambda Memory** (more CPU power)
2. **Optimize Bedrock Prompts** (reduce token usage)  
3. **Implement Async Processing** (for large files)

### High Costs

#### Problem: Unexpected AWS bills

#### Cost Analysis
```bash
# Check current month costs by service
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE
```

#### Cost Optimization
1. **DynamoDB**: Use on-demand pricing (already configured)
2. **S3**: Implement lifecycle policies for old files
3. **CloudFront**: Monitor transfer costs
4. **Lambda**: Right-size memory allocation
5. **Bedrock**: Monitor token usage and optimize prompts

## 📞 Getting Help

### Before Seeking Help

1. **Check CloudWatch Logs**: 90% of issues are visible in logs
2. **Verify Quotas**: Especially Bedrock quotas for new accounts
3. **Test Health Endpoint**: `curl https://your-api-url/api/health`
4. **Check AWS Service Status**: https://status.aws.amazon.com/

### Information to Include in Bug Reports

```bash
# 1. CDK version
cdk --version

# 2. AWS region and account
aws sts get-caller-identity

# 3. Recent CloudWatch logs
aws logs filter-log-events \
  --log-group-name "/aws/lambda/ArchLens-Compute-APILambda" \
  --start-time $(date -d '10 minutes ago' +%s)000

# 4. Stack deployment status
aws cloudformation describe-stacks \
  --stack-name ArchLens-Compute \
  --query 'Stacks[0].StackStatus'
```

### Emergency Recovery

If everything breaks:

```bash
# 1. Destroy all stacks
cd infrastructure
cdk destroy --all

# 2. Clean up any orphaned resources manually in AWS Console

# 3. Bootstrap and redeploy
cdk bootstrap
cdk deploy --all --require-approval never

# 4. Rebuild and redeploy frontend
cd ../frontend
npm run build
aws s3 sync out/ s3://your-new-bucket-name --delete
```

---

**Remember**: Most issues are related to AWS quotas and permissions. Always check these first!