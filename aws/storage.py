import os
import json
from typing import Any, BinaryIO
import boto3
from botocore.exceptions import ClientError

class S3Storage:
    """Handles all interactions with AWS S3."""
    
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.bucket_name = os.getenv('S3_BUCKET_NAME')

    def upload_json(self, data: Any, s3_key: str) -> bool:
        """Uploads serializable Python objects as JSON to S3."""
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=json.dumps(data),
                ContentType='application/json'
            )
            return True
        except ClientError as e:
            raise Exception(f"Failed to upload JSON to S3: {e}") from e

    def upload_stream(self, stream: BinaryIO, s3_key: str, content_type: str = 'application/zip') -> bool:
        """Uploads a file-like stream directly to S3."""
        try:
            self.s3_client.upload_fileobj(
                stream,
                self.bucket_name,
                s3_key,
                ExtraArgs={'ContentType': content_type}
            )
            return True
        except ClientError as e:
            raise Exception(f"Failed to stream file to S3: {e}") from e

    def check_config(self) -> bool:
        """Fail-fast check for required configuration."""
        return bool(self.bucket_name)