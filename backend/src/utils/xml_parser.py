import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any
import re
import logging

logger = logging.getLogger(__name__)

class DrawIOParser:
    """Parser for draw.io XML files to extract AWS architecture information"""
    
    def __init__(self):
        self.aws_services = {
            # Common AWS service patterns in draw.io
            'ec2': ['EC2', 'Amazon EC2', 'Elastic Compute'],
            's3': ['S3', 'Amazon S3', 'Simple Storage'],
            'lambda': ['Lambda', 'AWS Lambda', 'λ'],
            'rds': ['RDS', 'Amazon RDS', 'Relational Database'],
            'apigateway': ['API Gateway', 'Amazon API Gateway'],
            'cloudfront': ['CloudFront', 'Amazon CloudFront'],
            'route53': ['Route 53', 'Amazon Route 53'],
            'elb': ['ELB', 'Load Balancer', 'Application Load Balancer', 'Network Load Balancer'],
            'vpc': ['VPC', 'Virtual Private Cloud'],
            'iam': ['IAM', 'Identity and Access Management'],
            'cloudwatch': ['CloudWatch', 'Amazon CloudWatch'],
            'sns': ['SNS', 'Simple Notification Service'],
            'sqs': ['SQS', 'Simple Queue Service'],
            'dynamodb': ['DynamoDB', 'Amazon DynamoDB'],
            'kinesis': ['Kinesis', 'Amazon Kinesis'],
            'elasticsearch': ['Elasticsearch', 'Amazon Elasticsearch', 'OpenSearch'],
            'redshift': ['Redshift', 'Amazon Redshift'],
            'ecs': ['ECS', 'Elastic Container Service'],
            'eks': ['EKS', 'Elastic Kubernetes Service'],
            'fargate': ['Fargate', 'AWS Fargate'],
            'secretsmanager': ['Secrets Manager', 'AWS Secrets Manager'],
            'kms': ['KMS', 'Key Management Service'],
            'waf': ['WAF', 'Web Application Firewall'],
            'shield': ['Shield', 'AWS Shield'],
            'cognito': ['Cognito', 'Amazon Cognito'],
            'acm': ['ACM', 'Certificate Manager']
        }
        
    def parse(self, xml_content: str) -> Dict[str, Any]:
        """Parse draw.io XML and extract architecture information"""
        try:
            # Parse XML
            root = ET.fromstring(xml_content)
            
            # Extract diagram information
            diagram_info = self._extract_diagram_info(root)
            
            # Extract AWS services
            services = self._extract_aws_services(root)
            
            # Extract connections/relationships
            connections = self._extract_connections(root)
            
            # Analyze security configurations
            security_analysis = self._analyze_security_configurations(services, connections)
            
            return {
                'diagram_info': diagram_info,
                'services': services,
                'connections': connections,
                'security_analysis': security_analysis,
                'raw_elements': len(root.findall('.//mxCell'))  # Total elements count
            }
            
        except ET.ParseError as e:
            logger.error(f"XML parsing error: {e}")
            raise ValueError(f"Invalid XML format: {e}")
        except Exception as e:
            logger.error(f"Parsing error: {e}")
            raise ValueError(f"Failed to parse diagram: {e}")
    
    def _extract_diagram_info(self, root: ET.Element) -> Dict[str, Any]:
        """Extract basic diagram information"""
        info = {
            'title': 'Unknown',
            'pages': 0,
            'total_elements': 0
        }
        
        # Try to find diagram title
        diagram_elem = root.find('.//diagram')
        if diagram_elem is not None:
            name = diagram_elem.get('name')
            if name:
                info['title'] = name
        
        # Count pages and elements
        info['pages'] = len(root.findall('.//diagram'))
        info['total_elements'] = len(root.findall('.//mxCell'))
        
        return info
    
    def _extract_aws_services(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Extract AWS services from the diagram"""
        services = []
        
        # Find all cells with values (text content)
        cells = root.findall('.//mxCell[@value]')
        
        for cell in cells:
            value = cell.get('value', '').strip()
            if not value:
                continue
                
            # Check if this cell represents an AWS service
            service_type = self._identify_aws_service(value)
            if service_type:
                # Extract geometry information
                geometry = cell.find('mxGeometry')
                position = {'x': 0, 'y': 0, 'width': 0, 'height': 0}
                if geometry is not None:
                    position = {
                        'x': float(geometry.get('x', 0)),
                        'y': float(geometry.get('y', 0)),
                        'width': float(geometry.get('width', 0)),
                        'height': float(geometry.get('height', 0))
                    }
                
                service = {
                    'id': cell.get('id'),
                    'type': service_type,
                    'label': value,
                    'position': position,
                    'style': cell.get('style', ''),
                    'security_relevant': self._is_security_relevant(service_type)
                }
                
                services.append(service)
        
        return services
    
    def _extract_connections(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Extract connections between services"""
        connections = []
        
        # Find all edges (connections)
        edges = root.findall('.//mxCell[@edge]')
        
        for edge in edges:
            source = edge.get('source')
            target = edge.get('target')
            
            if source and target:
                connection = {
                    'id': edge.get('id'),
                    'source': source,
                    'target': target,
                    'label': edge.get('value', '').strip(),
                    'style': edge.get('style', '')
                }
                connections.append(connection)
        
        return connections
    
    def _identify_aws_service(self, text: str) -> Optional[str]:
        """Identify AWS service type from text"""
        text_lower = text.lower()
        
        for service_key, patterns in self.aws_services.items():
            for pattern in patterns:
                if pattern.lower() in text_lower:
                    return service_key
        
        return None
    
    def _is_security_relevant(self, service_type: str) -> bool:
        """Check if service type is security relevant"""
        security_relevant_services = {
            'iam', 'kms', 'secretsmanager', 'waf', 'shield', 
            'cognito', 'acm', 'vpc', 's3', 'ec2'
        }
        return service_type in security_relevant_services
    
    def _analyze_security_configurations(self, services: List[Dict], connections: List[Dict]) -> Dict[str, Any]:
        """Analyze security configurations from extracted data"""
        analysis = {
            'public_services': [],
            'unencrypted_services': [],
            'missing_security_groups': [],
            'internet_facing': [],
            'security_service_count': 0
        }
        
        # Count security services
        security_services = [s for s in services if s.get('security_relevant', False)]
        analysis['security_service_count'] = len(security_services)
        
        # Check for potential security issues
        for service in services:
            service_type = service.get('type')
            label = service.get('label', '').lower()
            
            # Check for public access indicators
            if any(keyword in label for keyword in ['public', 'internet', 'external']):
                analysis['public_services'].append(service)
            
            # Check for S3 buckets (common security concern)
            if service_type == 's3':
                if 'private' not in label and 'encrypted' not in label:
                    analysis['unencrypted_services'].append(service)
        
        return analysis
    
    def generate_architecture_description(self, parsed_data: Dict[str, Any]) -> str:
        """Generate a human-readable description of the architecture"""
        services = parsed_data.get('services', [])
        connections = parsed_data.get('connections', [])
        diagram_info = parsed_data.get('diagram_info', {})
        
        if not services:
            return "No AWS services were detected in the uploaded diagram. Please ensure your diagram contains AWS service components with recognizable labels."
        
        # Group services by type
        service_counts = {}
        service_types = []
        
        for service in services:
            service_type = service.get('type', 'unknown')
            if service_type not in service_counts:
                service_counts[service_type] = 0
                service_types.append(service_type)
            service_counts[service_type] += 1
        
        # Start building description
        description_parts = []
        
        # Title and overview
        title = diagram_info.get('title', 'Architecture Diagram')
        if title != 'Unknown':
            description_parts.append(f"**{title}**")
        
        total_services = len(services)
        total_connections = len(connections)
        
        description_parts.append(f"This architecture diagram contains **{total_services} AWS services** with **{total_connections} connections** between components.")
        
        # Service breakdown
        if service_counts:
            service_list = []
            for service_type in service_types:
                count = service_counts[service_type]
                service_name = self._get_service_display_name(service_type)
                if count == 1:
                    service_list.append(f"1 {service_name}")
                else:
                    service_list.append(f"{count} {service_name} instances")
            
            if len(service_list) > 1:
                services_text = ", ".join(service_list[:-1]) + f", and {service_list[-1]}"
            else:
                services_text = service_list[0]
            
            description_parts.append(f"The architecture includes: {services_text}.")
        
        # Architecture patterns
        patterns = self._identify_architecture_patterns(services, connections)
        if patterns:
            description_parts.append(f"**Architecture Patterns Detected:** {', '.join(patterns)}")
        
        # Data flow description
        data_flow = self._describe_data_flow(services, connections)
        if data_flow:
            description_parts.append(f"**Data Flow:** {data_flow}")
        
        # Security highlights
        security_highlights = self._describe_security_aspects(services)
        if security_highlights:
            description_parts.append(f"**Security Aspects:** {security_highlights}")
        
        return "\n\n".join(description_parts)
    
    def _get_service_display_name(self, service_type: str) -> str:
        """Get human-readable service name"""
        display_names = {
            'ec2': 'EC2 instance',
            's3': 'S3 bucket',
            'lambda': 'Lambda function',
            'rds': 'RDS database',
            'apigateway': 'API Gateway',
            'cloudfront': 'CloudFront distribution',
            'route53': 'Route 53 DNS',
            'elb': 'Load Balancer',
            'vpc': 'VPC network',
            'iam': 'IAM service',
            'cloudwatch': 'CloudWatch monitoring',
            'sns': 'SNS notification service',
            'sqs': 'SQS queue',
            'dynamodb': 'DynamoDB table',
            'kinesis': 'Kinesis stream',
            'elasticsearch': 'Elasticsearch/OpenSearch cluster',
            'redshift': 'Redshift data warehouse',
            'ecs': 'ECS container service',
            'eks': 'EKS Kubernetes cluster',
            'fargate': 'Fargate container',
            'secretsmanager': 'Secrets Manager',
            'kms': 'KMS encryption service',
            'waf': 'WAF firewall',
            'shield': 'Shield DDoS protection',
            'cognito': 'Cognito identity service',
            'acm': 'Certificate Manager'
        }
        return display_names.get(service_type, f'{service_type.upper()} service')
    
    def _identify_architecture_patterns(self, services: list, connections: list) -> list:
        """Identify common architecture patterns"""
        patterns = []
        service_types = {s.get('type') for s in services}
        
        # Web application pattern
        if 'elb' in service_types and 'ec2' in service_types:
            patterns.append("Load-balanced web application")
        
        # Serverless pattern
        if 'lambda' in service_types and 'apigateway' in service_types:
            patterns.append("Serverless API")
        
        # Microservices pattern
        lambda_count = len([s for s in services if s.get('type') == 'lambda'])
        if lambda_count > 2:
            patterns.append("Microservices architecture")
        
        # Data processing pattern
        if 'kinesis' in service_types or 'sqs' in service_types:
            patterns.append("Event-driven processing")
        
        # CDN pattern
        if 'cloudfront' in service_types:
            patterns.append("Content delivery network")
        
        # Database pattern
        db_services = {'rds', 'dynamodb', 'elasticsearch', 'redshift'}
        if db_services.intersection(service_types):
            patterns.append("Multi-tier data storage")
        
        return patterns
    
    def _describe_data_flow(self, services: list, connections: list) -> str:
        """Describe the data flow in the architecture"""
        if not connections:
            return "No explicit connections defined between services."
        
        # Find entry points (services with incoming but few outgoing connections)
        service_ids = {s.get('id') for s in services}
        incoming_counts = {}
        outgoing_counts = {}
        
        for conn in connections:
            source = conn.get('source')
            target = conn.get('target')
            
            if target in service_ids:
                incoming_counts[target] = incoming_counts.get(target, 0) + 1
            if source in service_ids:
                outgoing_counts[source] = outgoing_counts.get(source, 0) + 1
        
        # Identify flow patterns
        entry_points = []
        endpoints = []
        
        for service in services:
            service_id = service.get('id')
            incoming = incoming_counts.get(service_id, 0)
            outgoing = outgoing_counts.get(service_id, 0)
            
            if incoming == 0 and outgoing > 0:
                entry_points.append(service.get('type', 'unknown'))
            elif outgoing == 0 and incoming > 0:
                endpoints.append(service.get('type', 'unknown'))
        
        flow_description = []
        if entry_points:
            entry_names = [self._get_service_display_name(ep) for ep in entry_points]
            flow_description.append(f"Traffic enters through {', '.join(entry_names)}")
        
        if endpoints:
            endpoint_names = [self._get_service_display_name(ep) for ep in endpoints]
            flow_description.append(f"and flows to {', '.join(endpoint_names)}")
        
        if flow_description:
            return " ".join(flow_description) + "."
        
        return f"Complex interconnected architecture with {len(connections)} connections between services."
    
    def _describe_security_aspects(self, services: list) -> str:
        """Describe security aspects of the architecture"""
        security_aspects = []
        service_types = {s.get('type') for s in services}
        
        # Check for security services
        if 'iam' in service_types:
            security_aspects.append("IAM access control")
        if 'waf' in service_types:
            security_aspects.append("WAF web protection")
        if 'kms' in service_types:
            security_aspects.append("KMS encryption")
        if 'secretsmanager' in service_types:
            security_aspects.append("Secrets Manager")
        if 'cognito' in service_types:
            security_aspects.append("Cognito authentication")
        
        # Check for VPC
        if 'vpc' in service_types:
            security_aspects.append("VPC network isolation")
        
        # Check for monitoring
        if 'cloudwatch' in service_types:
            security_aspects.append("CloudWatch monitoring")
        
        if not security_aspects:
            return "No explicit security services identified in the diagram."
        
        return f"Includes {', '.join(security_aspects)}."