import boto3
import json
import logging
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError
from ..models.analysis import AnalysisRecord, AnalysisStatus

logger = logging.getLogger(__name__)

class StorageService:
    """Service for managing S3 and DynamoDB operations"""
    
    def __init__(self, region: str = 'us-east-1'):
        self.region = region
        self.s3_client = boto3.client('s3', region_name=region)
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
    
    def upload_file_to_s3(self, bucket_name: str, key: str, file_content: bytes, content_type: str = 'application/xml') -> str:
        """Upload file to S3 bucket"""
        try:
            self.s3_client.put_object(
                Bucket=bucket_name,
                Key=key,
                Body=file_content,
                ContentType=content_type,
                ServerSideEncryption='AES256'
            )
            return f"s3://{bucket_name}/{key}"
        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            raise Exception(f"File upload failed: {str(e)}")
    
    def get_file_from_s3(self, bucket_name: str, key: str) -> bytes:
        """Download file from S3 bucket"""
        try:
            response = self.s3_client.get_object(Bucket=bucket_name, Key=key)
            return response['Body'].read()
        except ClientError as e:
            logger.error(f"S3 download failed: {e}")
            raise Exception(f"File download failed: {str(e)}")
    
    def delete_file_from_s3(self, bucket_name: str, key: str) -> bool:
        """Delete file from S3 bucket"""
        try:
            self.s3_client.delete_object(Bucket=bucket_name, Key=key)
            return True
        except ClientError as e:
            logger.error(f"S3 delete failed: {e}")
            return False
    
    def save_analysis_record(self, table_name: str, record: AnalysisRecord) -> bool:
        """Save analysis record to DynamoDB"""
        try:
            table = self.dynamodb.Table(table_name)
            
            # Convert Pydantic model to dict
            item = record.model_dump()
            
            # Remove None values
            item = {k: v for k, v in item.items() if v is not None}
            
            table.put_item(Item=item)
            return True
            
        except ClientError as e:
            logger.error(f"DynamoDB save failed: {e}")
            raise Exception(f"Failed to save analysis record: {str(e)}")
    
    def get_analysis_record(self, table_name: str, analysis_id: str) -> Optional[AnalysisRecord]:
        """Get analysis record from DynamoDB"""
        try:
            table = self.dynamodb.Table(table_name)
            
            response = table.get_item(
                Key={'analysis_id': analysis_id}
            )
            
            if 'Item' in response:
                return AnalysisRecord(**response['Item'])
            
            return None
            
        except ClientError as e:
            logger.error(f"DynamoDB get failed: {e}")
            raise Exception(f"Failed to get analysis record: {str(e)}")
    
    def update_analysis_status(self, table_name: str, analysis_id: str, status: AnalysisStatus, 
                             results: Optional[Dict[str, Any]] = None, 
                             error_message: Optional[str] = None,
                             description: Optional[str] = None) -> bool:
        """Update analysis record status"""
        try:
            table = self.dynamodb.Table(table_name)
            
            update_expression = "SET #status = :status"
            expression_values = {':status': status.value}
            expression_names = {'#status': 'status'}
            
            if results:
                update_expression += ", results = :results"
                expression_values[':results'] = results
            
            if error_message:
                update_expression += ", error_message = :error_message"
                expression_values[':error_message'] = error_message
            
            if description:
                update_expression += ", description = :description"
                expression_values[':description'] = description
            
            table.update_item(
                Key={'analysis_id': analysis_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values,
                ExpressionAttributeNames=expression_names
            )
            
            return True
            
        except ClientError as e:
            logger.error(f"DynamoDB update failed: {e}")
            raise Exception(f"Failed to update analysis record: {str(e)}")
    
    def list_recent_analyses(self, table_name: str, limit: int = 10) -> list:
        """List recent analyses by status"""
        try:
            table = self.dynamodb.Table(table_name)
            
            # Query by status index to get recent analyses
            response = table.scan(
                IndexName='status-timestamp-index',
                Limit=limit,
                ScanIndexForward=False  # Descending order by timestamp
            )
            
            analyses = []
            for item in response.get('Items', []):
                try:
                    analyses.append(AnalysisRecord(**item))
                except Exception as e:
                    logger.warning(f"Failed to parse analysis record: {e}")
                    continue
            
            return analyses
            
        except ClientError as e:
            logger.error(f"DynamoDB scan failed: {e}")
            return []
    
    def cleanup_expired_files(self, bucket_name: str, hours: int = 48) -> int:
        """Clean up expired files from S3 (older than specified hours)"""
        try:
            from datetime import datetime, timedelta
            
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            response = self.s3_client.list_objects_v2(Bucket=bucket_name)
            deleted_count = 0
            
            for obj in response.get('Contents', []):
                if obj['LastModified'].replace(tzinfo=None) < cutoff_time:
                    self.s3_client.delete_object(Bucket=bucket_name, Key=obj['Key'])
                    deleted_count += 1
            
            logger.info(f"Cleaned up {deleted_count} expired files from {bucket_name}")
            return deleted_count
            
        except ClientError as e:
            logger.error(f"Cleanup failed: {e}")
            return 0