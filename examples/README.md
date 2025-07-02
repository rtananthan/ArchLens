# Example Architecture Files

This directory contains sample draw.io architecture files for testing ArchLens.

## sample-aws-architecture.xml

A comprehensive AWS architecture diagram that demonstrates:

**Services Included:**
- Internet Gateway (public entry point)
- VPC with multiple subnets
- Application Load Balancer (public subnet)
- EC2 Web Server (private subnet)
- RDS MySQL Database (database subnet)
- S3 Bucket (marked as public read)
- Lambda Function (serverless API)
- API Gateway (REST API)
- DynamoDB (session storage)
- CloudWatch (monitoring)

**Architecture Patterns:**
- Load-balanced web application
- Serverless API backend
- Multi-tier data storage
- Event-driven processing

**Expected Description Output:**
When uploaded to ArchLens, this file should generate a description similar to:

```
**AWS Security Architecture**

This architecture diagram contains 10 AWS services with 5 connections between components.

The architecture includes: 1 Internet Gateway, 1 VPC network, 1 Load Balancer, 1 EC2 instance, 1 RDS database, 1 S3 bucket, 1 Lambda function, 1 API Gateway, 1 DynamoDB table, and 1 CloudWatch monitoring.

Architecture Patterns Detected: Load-balanced web application, Serverless API, Multi-tier data storage

Data Flow: Traffic enters through Internet Gateway and flows to DynamoDB table.

Security Aspects: Includes VPC network isolation, CloudWatch monitoring.
```

**Security Issues to Expect:**
- HIGH: S3 Bucket with public read access
- MEDIUM: No explicit security services (WAF, IAM) shown
- LOW: Missing encryption indicators

This file is perfect for testing the immediate architecture description feature and the full security analysis pipeline.

## Testing the Description Feature

1. Upload the sample file to ArchLens
2. Observe the immediate description that appears
3. Continue to full security analysis
4. Compare results with expected outputs

The description feature should:
- Parse all AWS services correctly
- Identify architecture patterns
- Describe data flow between components
- Highlight security aspects
- Present information in a user-friendly format