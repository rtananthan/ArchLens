# ArchLens CloudFormation Deployment

## 🚀 Alternative Deployment Method

This directory contains CloudFormation templates as an alternative to the CDK deployment method. These templates are ideal for enterprise environments where Infrastructure as Code (IaC) governance and standardized deployments are required.

## 📁 Template Structure

```
cloudformation/
├── 01-storage.yaml          # S3 buckets and DynamoDB table
├── 02-ai.yaml               # Amazon Bedrock agent configuration  
├── 03-compute.yaml          # Lambda functions and API Gateway
├── 04-frontend.yaml         # CloudFront distribution and S3 hosting
├── deploy.sh                # Automated deployment script
├── README.md               # This file
└── parameters/             # Parameter files for different environments
    ├── dev.json
    ├── staging.json
    └── prod.json
```

## 🔐 Enterprise Permission Requirements

**Before deploying**, request these permissions from your Cloud Platform team:

### Critical Services Required:
- **Amazon Bedrock** (AI analysis) - Requires quota increase
- **CloudFormation** (Infrastructure deployment)
- **Lambda + API Gateway** (Serverless backend)
- **S3 + DynamoDB** (Storage layer)
- **CloudFront** (CDN for global performance)
- **IAM** (Service roles and policies)

**📋 Complete permission details**: See `../AWS_ENTERPRISE_PERMISSIONS_REQUEST.md`

## ⚡ Quick Deployment

### Prerequisites
1. AWS CLI configured with appropriate permissions
2. Bedrock quotas increased (1 → 100 requests/minute)
3. S3 bucket for Lambda deployment artifacts

### One-Command Deployment
```bash
# Create deployment bucket (one-time setup)
aws s3 mb s3://archlens-deployment-$(aws sts get-caller-identity --query Account --output text)-us-east-1

# Deploy everything
./deploy.sh prod us-east-1 archlens-deployment-$(aws sts get-caller-identity --query Account --output text)-us-east-1
```

### Manual Step-by-Step Deployment

#### 1. Package Lambda Code
```bash
cd ../backend_clean
zip -r ../archlens-backend.zip .
aws s3 cp ../archlens-backend.zip s3://YOUR-DEPLOYMENT-BUCKET/lambda/
cd ../cloudformation
```

#### 2. Deploy Storage Stack
```bash
aws cloudformation create-stack \
  --stack-name ArchLens-Storage-Production \
  --template-body file://01-storage.yaml \
  --parameters ParameterKey=Environment,ParameterValue=prod
```

#### 3. Deploy AI Stack (Requires Bedrock permissions)
```bash
aws cloudformation create-stack \
  --stack-name ArchLens-AI-Production \
  --template-body file://02-ai.yaml \
  --parameters ParameterKey=Environment,ParameterValue=prod \
  --capabilities CAPABILITY_NAMED_IAM
```

#### 4. Deploy Compute Stack
```bash
aws cloudformation create-stack \
  --stack-name ArchLens-Compute-Production \
  --template-body file://03-compute.yaml \
  --parameters ParameterKey=Environment,ParameterValue=prod \
    ParameterKey=LambdaCodeBucket,ParameterValue=YOUR-DEPLOYMENT-BUCKET \
  --capabilities CAPABILITY_NAMED_IAM
```

#### 5. Deploy Frontend Stack
```bash
aws cloudformation create-stack \
  --stack-name ArchLens-Frontend-Production \
  --template-body file://04-frontend.yaml \
  --parameters ParameterKey=Environment,ParameterValue=prod
```

#### 6. Deploy Frontend Assets
```bash
cd ../frontend
npm run build
aws s3 sync out/ s3://FRONTEND-BUCKET-NAME --delete
```

## 🌍 Multi-Environment Deployment

### Development Environment
```bash
./deploy.sh dev us-east-1 archlens-deployment-ACCOUNT-us-east-1
```

### Staging Environment  
```bash
./deploy.sh staging us-east-1 archlens-deployment-ACCOUNT-us-east-1
```

### Production Environment
```bash
./deploy.sh prod us-east-1 archlens-deployment-ACCOUNT-us-east-1
```

## 🔧 Configuration Parameters

### Environment Variables (Auto-configured)
| Parameter | Description | Example |
|-----------|-------------|---------|
| `UPLOAD_BUCKET` | S3 bucket for uploaded files | `archlens-uploads-123456-us-east-1` |
| `ANALYSIS_TABLE` | DynamoDB table for results | `ArchLens-Analysis-us-east-1` |
| `BEDROCK_AGENT_ID` | AI agent identifier | `BQ2AJX1QNF` |
| `BEDROCK_AGENT_ALIAS_ID` | Agent alias | `TSTALIASID` |

### Regional Deployment
```bash
# Deploy to different regions (ensure Bedrock availability)
./deploy.sh prod us-west-2 archlens-deployment-ACCOUNT-us-west-2
./deploy.sh prod eu-west-1 archlens-deployment-ACCOUNT-eu-west-1
./deploy.sh prod ap-southeast-2 archlens-deployment-ACCOUNT-ap-southeast-2
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. Bedrock Quota Limitations
**Error**: `throttlingException: Your request rate is too high`

**Solution**: Create AWS Support case for quota increase:
```bash
# Check current quotas
aws service-quotas get-service-quota --service-code bedrock --quota-code L-254CACF4
```

#### 2. CloudFormation Permission Errors
**Error**: `User is not authorized to perform: cloudformation:CreateStack`

**Solution**: Request permissions from Cloud Platform team using `../AWS_ENTERPRISE_PERMISSIONS_REQUEST.md`

#### 3. Lambda Deployment Package Issues
**Error**: `The specified key does not exist`

**Solution**: Ensure Lambda package is uploaded:
```bash
aws s3 ls s3://YOUR-DEPLOYMENT-BUCKET/lambda/archlens-backend.zip
```

#### 4. Stack Dependencies
**Error**: `Export cannot be deleted as it is in use by another stack`

**Solution**: Delete stacks in reverse order:
```bash
aws cloudformation delete-stack --stack-name ArchLens-Frontend-Production
aws cloudformation delete-stack --stack-name ArchLens-Compute-Production  
aws cloudformation delete-stack --stack-name ArchLens-AI-Production
aws cloudformation delete-stack --stack-name ArchLens-Storage-Production
```

### Stack Status Monitoring
```bash
# Monitor deployment progress
aws cloudformation describe-stacks --stack-name ArchLens-Storage-Production
aws cloudformation describe-stack-events --stack-name ArchLens-Storage-Production
```

### Health Checks
```bash
# Test API after deployment
API_URL=$(aws cloudformation describe-stacks \
  --stack-name ArchLens-Compute-Production \
  --query 'Stacks[0].Outputs[?OutputKey==`APIGatewayURL`].OutputValue' \
  --output text)

curl $API_URL/api/health
```

## 🎯 Production Considerations

### Security Hardening
- [ ] Enable CloudTrail for audit logging
- [ ] Configure VPC endpoints for S3/DynamoDB access
- [ ] Implement custom domain with SSL certificate
- [ ] Set up CloudWatch alarms for monitoring
- [ ] Enable AWS Config for compliance monitoring

### Performance Optimization
- [ ] Configure Lambda reserved concurrency
- [ ] Implement DynamoDB auto-scaling
- [ ] Optimize CloudFront caching policies
- [ ] Monitor and adjust Lambda memory allocation

### Cost Optimization
- [ ] Implement S3 lifecycle policies
- [ ] Configure DynamoDB TTL (already included)
- [ ] Monitor Bedrock usage and costs
- [ ] Set up billing alerts

## 🔄 Updates and Maintenance

### Updating Infrastructure
```bash
# Update specific stack
aws cloudformation update-stack \
  --stack-name ArchLens-Compute-Production \
  --template-body file://03-compute.yaml \
  --parameters ParameterKey=Environment,ParameterValue=prod \
  --capabilities CAPABILITY_NAMED_IAM
```

### Updating Lambda Code
```bash
# Package and upload new code
cd ../backend_clean
zip -r ../archlens-backend.zip .
aws s3 cp ../archlens-backend.zip s3://YOUR-DEPLOYMENT-BUCKET/lambda/

# Update Lambda function
aws lambda update-function-code \
  --function-name ArchLens-API-Production \
  --s3-bucket YOUR-DEPLOYMENT-BUCKET \
  --s3-key lambda/archlens-backend.zip
```

### Updating Frontend
```bash
cd ../frontend
npm run build
aws s3 sync out/ s3://FRONTEND-BUCKET-NAME --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id DISTRIBUTION-ID \
  --paths "/*"
```

## 📊 Monitoring and Observability

### CloudWatch Dashboards
- Lambda function metrics (duration, errors, invocations)
- API Gateway metrics (request count, latency, errors)
- DynamoDB metrics (consumed capacity, throttling)
- S3 metrics (requests, storage, transfer)
- Bedrock usage metrics

### Log Groups
- `/aws/lambda/ArchLens-API-Production`
- `/aws/lambda/ArchLens-Processor-Production`
- `/aws/apigateway/ArchLens-API-Production`
- `/aws/bedrock/agents/ArchLens-SecurityAnalysis`

### Alerts Setup
```bash
# Example: Create high error rate alarm
aws cloudwatch put-metric-alarm \
  --alarm-name "ArchLens-HighErrorRate" \
  --alarm-description "High error rate in API Lambda" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold
```

## 💰 Cost Estimation

### Monthly Cost Breakdown (Production)
| Service | Estimated Cost | Notes |
|---------|----------------|-------|
| **Bedrock (Claude 3.5)** | $200-250 | Based on 50-100 req/hour |
| **Lambda** | $20-40 | Execution time and requests |
| **API Gateway** | $10-20 | REST API requests |
| **DynamoDB** | $5-15 | On-demand billing |
| **S3 Storage** | $5-10 | File storage and transfer |
| **CloudFront** | $10-30 | Global CDN distribution |
| **Total** | **$250-365/month** | For active production usage |

### Cost Optimization Tips
1. **Monitor Bedrock usage** - Primary cost driver
2. **Optimize Lambda memory** - Right-size for performance
3. **Use S3 lifecycle policies** - Archive old files
4. **Monitor API Gateway requests** - Implement caching where possible

## 📞 Support

### Getting Help
1. **Check CloudWatch Logs** - First line of troubleshooting
2. **Review CloudFormation Events** - For deployment issues
3. **AWS Support** - For service limits and quotas
4. **Internal Documentation** - Company-specific deployment guides

### Escalation Path
1. Application issues → Development team
2. Infrastructure issues → Cloud Platform team  
3. AWS service issues → AWS Support
4. Security concerns → Security team

---

**💡 Pro Tip**: Always test deployments in a development environment before deploying to production. The CloudFormation templates include comprehensive tagging and resource naming for easy identification and cost allocation.