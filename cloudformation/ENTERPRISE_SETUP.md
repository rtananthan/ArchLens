# Enterprise Setup Guide

## 📋 Required Documents for Cloud Platform Team

The following documents are needed for enterprise deployment but are **not included in the Git repository** for security reasons:

### 🔐 Generate Required Documents

Run this command to create the enterprise permission request documents:

```bash
# This will create the required permission documents locally
# (These files are gitignored for security)
echo "Creating enterprise setup documents..."

# You can find templates and examples in the docs/ directory
# or request them from the development team
```

### 📄 Required Files (Not in Git)

1. **`AWS_ENTERPRISE_PERMISSIONS_REQUEST.md`**
   - Complete IAM permission policies for Cloud Platform team
   - Bedrock quota increase requirements
   - AWS Support case templates
   - Cost estimates and security compliance details

2. **`AWS_BEDROCK_QUOTA_INCREASE_GUIDE.md`**
   - Step-by-step guide for increasing Bedrock quotas
   - Console and CLI methods
   - Support case templates and troubleshooting

### 🚀 How to Get These Documents

**Option 1: Request from Development Team**
```bash
# Contact the development team for the latest versions
# These contain sensitive account-specific information
```

**Option 2: Generate from Templates**
```bash
# Use the deployment documentation to create customized versions
# for your specific AWS account and requirements
```

### ⚠️ Why These Files Are Gitignored

- **Security**: Contain account-specific ARNs and sensitive deployment details
- **Compliance**: Enterprise permission requests often include internal cost centers and team contacts  
- **Customization**: Need to be tailored for each organization's specific AWS setup
- **Sensitive Data**: May include internal business justifications and contact information

### 📞 Getting Started

1. **Contact Development Team** for enterprise setup documents
2. **Customize** permission requests for your organization
3. **Submit** to Cloud Platform team with all required details
4. **Deploy** using CloudFormation templates once permissions are approved

---

**Note**: All technical deployment information is available in the public CloudFormation templates and documentation. Only the enterprise-specific permission requests are kept private.