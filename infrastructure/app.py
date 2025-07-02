#!/usr/bin/env python3
import os
import aws_cdk as cdk
from stacks.storage_stack import StorageStack
from stacks.compute_stack import ComputeStack
from stacks.ai_stack import AIStack
from stacks.frontend_stack import FrontendStack
from config.tags import get_common_tags, get_environment_specific_tags, get_cost_allocation_tags, validate_tags

app = cdk.App()

# Environment configuration
env = cdk.Environment(
    account=os.getenv('CDK_DEFAULT_ACCOUNT'),
    region=os.getenv('CDK_DEFAULT_REGION', 'us-east-1')
)

# Get environment from context
environment = app.node.try_get_context('environment') or 'dev'

# Build comprehensive tags
common_tags = get_common_tags(environment)
env_tags = get_environment_specific_tags(environment)
cost_tags = get_cost_allocation_tags('ENG-001', 'production')

# Merge all tags and validate
all_tags = {**common_tags, **env_tags, **cost_tags}
validated_tags = validate_tags(all_tags)

# Deploy stacks in order due to dependencies
storage_stack = StorageStack(
    app, 
    'ArchLens-Storage',
    env=env,
    tags=validated_tags,
    environment=environment
)

ai_stack = AIStack(
    app,
    'ArchLens-AI',
    env=env,
    tags=validated_tags,
    environment=environment
)

compute_stack = ComputeStack(
    app,
    'ArchLens-Compute',
    storage_stack=storage_stack,
    ai_stack=ai_stack,
    env=env,
    tags=validated_tags,
    environment=environment
)

frontend_stack = FrontendStack(
    app,
    'ArchLens-Frontend',
    api_gateway=compute_stack.api_gateway,
    env=env,
    tags=validated_tags,
    environment=environment
)

app.synth()