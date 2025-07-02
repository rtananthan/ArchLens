import boto3
import json
import logging
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError, BotoCoreError

logger = logging.getLogger(__name__)

class BedrockService:
    """Service for interacting with Amazon Bedrock for AI analysis"""
    
    def __init__(self, region: str = 'us-east-1'):
        self.region = region
        self.bedrock_runtime = boto3.client('bedrock-runtime', region_name=region)
        self.bedrock_agent_runtime = boto3.client('bedrock-agent-runtime', region_name=region)
    
    async def analyze_architecture(self, architecture_data: Dict[str, Any], agent_id: str, agent_alias_id: str) -> Dict[str, Any]:
        """Analyze architecture using Bedrock agent"""
        try:
            # Prepare the analysis prompt
            analysis_prompt = self._prepare_analysis_prompt(architecture_data)
            
            # Try agent first, fallback to direct model if agent fails
            try:
                result = await self._invoke_agent(analysis_prompt, agent_id, agent_alias_id)
            except Exception as agent_error:
                logger.warning(f"Agent invocation failed: {agent_error}, falling back to direct model")
                result = await self._invoke_model_direct(analysis_prompt)
            
            return result
            
        except Exception as e:
            logger.error(f"Bedrock analysis failed: {e}")
            raise Exception(f"AI analysis failed: {str(e)}")
    
    async def _invoke_agent(self, prompt: str, agent_id: str, agent_alias_id: str) -> Dict[str, Any]:
        """Invoke Bedrock agent for analysis"""
        try:
            response = self.bedrock_agent_runtime.invoke_agent(
                agentId=agent_id,
                agentAliasId=agent_alias_id,
                sessionId=f"analysis-session-{hash(prompt) % 10000}",
                inputText=prompt
            )
            
            # Parse streaming response
            result_text = ""
            for event in response['completion']:
                if 'chunk' in event:
                    chunk = event['chunk']
                    if 'bytes' in chunk:
                        result_text += chunk['bytes'].decode('utf-8')
            
            # Parse JSON response
            return self._parse_analysis_response(result_text)
            
        except ClientError as e:
            logger.error(f"Bedrock agent error: {e}")
            raise Exception(f"Bedrock agent invocation failed: {e}")
    
    async def _invoke_model_direct(self, prompt: str) -> Dict[str, Any]:
        """Direct model invocation as fallback"""
        try:
            # Use Claude 3 Sonnet for analysis
            model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
            
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4000,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.1
            }
            
            response = self.bedrock_runtime.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body)
            )
            
            response_body = json.loads(response['body'].read())
            result_text = response_body['content'][0]['text']
            
            return self._parse_analysis_response(result_text)
            
        except ClientError as e:
            logger.error(f"Direct model invocation error: {e}")
            raise Exception(f"Model invocation failed: {e}")
    
    def _prepare_analysis_prompt(self, architecture_data: Dict[str, Any]) -> str:
        """Prepare the analysis prompt for Bedrock"""
        services = architecture_data.get('services', [])
        connections = architecture_data.get('connections', [])
        security_analysis = architecture_data.get('security_analysis', {})
        
        prompt = f"""
You are an AWS security architecture expert. Analyze the following AWS architecture for security best practices.

ARCHITECTURE DETAILS:
- Total Services: {len(services)}
- Total Connections: {len(connections)}
- Diagram Title: {architecture_data.get('diagram_info', {}).get('title', 'Unknown')}

SERVICES IDENTIFIED:
{self._format_services(services)}

CONNECTIONS:
{self._format_connections(connections)}

SECURITY ANALYSIS FINDINGS:
{json.dumps(security_analysis, indent=2)}

Please provide a comprehensive security analysis following the AWS Well-Architected Framework Security Pillar. Focus on:

1. Data protection in transit and at rest
2. Identity and access management
3. Infrastructure protection
4. Detective controls
5. Incident response preparation

Return your analysis as a JSON object with this exact structure:
{{
    "analysis_id": "generated-analysis-id",
    "status": "completed",
    "timestamp": "{architecture_data.get('timestamp', '')}",
    "results": {{
        "overall_score": <float 0-10>,
        "security": {{
            "score": <float 0-10>,
            "issues": [
                {{
                    "severity": "HIGH|MEDIUM|LOW",
                    "component": "service or component name",
                    "issue": "description of security issue",
                    "recommendation": "specific remediation advice",
                    "aws_service": "AWS service name"
                }}
            ],
            "recommendations": [
                "general security improvement recommendations"
            ]
        }}
    }}
}}

Focus on actionable, specific recommendations based on the identified services and architecture patterns.
"""
        return prompt
    
    def _format_services(self, services: list) -> str:
        """Format services for the prompt"""
        if not services:
            return "No AWS services identified"
        
        formatted = []
        for service in services:
            formatted.append(f"- {service.get('type', 'unknown').upper()}: {service.get('label', 'No label')}")
        
        return "\n".join(formatted)
    
    def _format_connections(self, connections: list) -> str:
        """Format connections for the prompt"""
        if not connections:
            return "No connections identified"
        
        formatted = []
        for conn in connections:
            label = conn.get('label', 'unlabeled connection')
            formatted.append(f"- {conn.get('source', 'unknown')} -> {conn.get('target', 'unknown')}: {label}")
        
        return "\n".join(formatted)
    
    def _parse_analysis_response(self, response_text: str) -> Dict[str, Any]:
        """Parse the analysis response from Bedrock"""
        try:
            # Try to extract JSON from the response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                result = json.loads(json_str)
                
                # Validate the response structure
                if 'results' in result and 'security' in result['results']:
                    return result
            
            # If JSON parsing fails, create a structured response
            logger.warning("Could not parse JSON response, creating structured response")
            return self._create_fallback_response(response_text)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return self._create_fallback_response(response_text)
    
    def _create_fallback_response(self, response_text: str) -> Dict[str, Any]:
        """Create a fallback response structure"""
        return {
            "analysis_id": "fallback-analysis",
            "status": "completed",
            "results": {
                "overall_score": 5.0,
                "security": {
                    "score": 5.0,
                    "issues": [
                        {
                            "severity": "MEDIUM",
                            "component": "Analysis System",
                            "issue": "Unable to parse detailed analysis results",
                            "recommendation": "Manual review of architecture recommended",
                            "aws_service": "General"
                        }
                    ],
                    "recommendations": [
                        "Review the uploaded architecture diagram for security best practices",
                        "Ensure all services follow AWS Well-Architected Framework guidelines",
                        response_text[:500] + "..." if len(response_text) > 500 else response_text
                    ]
                }
            }
        }