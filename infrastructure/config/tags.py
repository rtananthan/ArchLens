"""
Centralized tagging configuration for ArchLens resources
"""

from typing import Dict, Any
import os

def get_common_tags(environment: str = 'dev', additional_tags: Dict[str, str] = None) -> Dict[str, str]:
    """
    Get common tags that should be applied to all ArchLens resources
    
    Args:
        environment: The deployment environment (dev, staging, prod)
        additional_tags: Additional tags to merge with common tags
    
    Returns:
        Dictionary of tags to apply to resources
    """
    
    # Base tags that apply to all resources (limited to most essential)
    common_tags = {
        # Core identification
        'Project': 'ArchLens',
        'Environment': environment,
        'Owner': 'ArchLens-Engineering-Team',
        'CostCenter': 'Engineering-Platform',
        
        # Compliance essentials
        'DataClassification': 'Internal',
        'BackupRequired': 'true',
        'EncryptionRequired': 'true',
        
        # Operational essentials
        'AutoShutdown': 'false',
        'AlertingEnabled': 'true',
        'Version': '1.0.0'
    }
    
    # Merge additional tags if provided
    if additional_tags:
        common_tags.update(additional_tags)
    
    return common_tags

def get_service_specific_tags(service_name: str, service_type: str, additional_tags: Dict[str, str] = None) -> Dict[str, str]:
    """
    Get tags specific to a particular service (essential only)
    
    Args:
        service_name: Name of the service (e.g., 'API-Lambda', 'Storage-S3')
        service_type: Type of service (e.g., 'compute', 'storage', 'ai', 'frontend')
        additional_tags: Additional service-specific tags (will be limited)
    
    Returns:
        Dictionary of service-specific tags (max 5 tags)
    """
    
    # Essential service tags only
    service_tags = {
        'ServiceName': service_name,
        'ServiceType': service_type,
    }
    
    # Add one essential tag per service type
    if service_type == 'compute':
        service_tags['ComputeType'] = 'Serverless'
    elif service_type == 'storage':
        service_tags['StorageType'] = 'S3-DynamoDB'
    elif service_type == 'ai':
        service_tags['AIService'] = 'Amazon-Bedrock'
    elif service_type == 'frontend':
        service_tags['DeliveryMethod'] = 'CloudFront-CDN'
    elif service_type == 'networking':
        service_tags['NetworkType'] = 'API-Gateway'
    
    # Add only 2 most essential additional tags
    if additional_tags:
        essential_keys = list(additional_tags.keys())[:2]
        for key in essential_keys:
            service_tags[key] = additional_tags[key]
    
    return service_tags

def get_service_category(service_type: str) -> str:
    """Map service type to broader category"""
    categories = {
        'compute': 'Application-Layer',
        'storage': 'Data-Layer',
        'ai': 'Intelligence-Layer',
        'frontend': 'Presentation-Layer',
        'networking': 'Network-Layer',
        'security': 'Security-Layer',
        'monitoring': 'Operations-Layer',
    }
    return categories.get(service_type, 'Infrastructure-Layer')

def get_environment_specific_tags(environment: str) -> Dict[str, str]:
    """
    Get tags specific to deployment environment (essential only)
    
    Args:
        environment: The deployment environment
    
    Returns:
        Dictionary of environment-specific tags (max 3 tags)
    """
    
    env_configs = {
        'dev': {
            'CostOptimization': 'aggressive',
            'LogRetention': '7days',
            'HighAvailability': 'false',
        },
        'staging': {
            'CostOptimization': 'moderate',
            'LogRetention': '30days',
            'HighAvailability': 'true',
        },
        'prod': {
            'CostOptimization': 'balanced',
            'LogRetention': '90days',
            'HighAvailability': 'true',
        }
    }
    
    return env_configs.get(environment, env_configs['dev'])

def get_cost_allocation_tags(cost_center: str, project_phase: str = 'production') -> Dict[str, str]:
    """
    Get tags for cost allocation (essential only)
    
    Args:
        cost_center: The cost center code
        project_phase: Current phase of the project
    
    Returns:
        Dictionary of cost allocation tags (max 3 tags)
    """
    
    return {
        'BudgetCode': f'ARCHLENS-{cost_center}',
        'ProjectPhase': project_phase,
        'CostCategory': 'Platform-Investment',
    }

def validate_tags(tags: Dict[str, str]) -> Dict[str, str]:
    """
    Validate and clean tags according to AWS requirements
    
    Args:
        tags: Dictionary of tags to validate
    
    Returns:
        Validated and cleaned tags dictionary
    """
    
    validated_tags = {}
    
    for key, value in tags.items():
        # AWS tag key requirements: 1-128 characters, alphanumeric, spaces, and +-=._:/@
        if len(key) > 128:
            key = key[:128]
        
        # AWS tag value requirements: 0-256 characters
        if len(str(value)) > 256:
            value = str(value)[:256]
        
        # Remove any invalid characters and ensure string type
        key = str(key).strip()
        value = str(value).strip()
        
        if key and value:  # Only add non-empty tags
            validated_tags[key] = value
    
    return validated_tags