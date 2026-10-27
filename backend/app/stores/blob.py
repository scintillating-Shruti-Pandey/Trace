from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import Settings


class BlobStore:
    def __init__(self, settings: Settings):
        self.bucket = settings.blob_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.blob_endpoint,
            aws_access_key_id=settings.blob_access_key,
            aws_secret_access_key=settings.blob_secret_key,
            region_name="us-east-1",
            config=Config(
                connect_timeout=3,
                read_timeout=10,
                retries={"max_attempts": 3, "mode": "standard"},
                s3={"addressing_style": "path"},
            ),
        )

    def ensure_bucket(self):
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in {"404", "NoSuchBucket"}:
                raise
            try:
                self.client.create_bucket(Bucket=self.bucket)
            except ClientError as race:
                if race.response["Error"]["Code"] != "BucketAlreadyOwnedByYou":
                    raise

    def put_file(self, path: Path, key: str):
        self.ensure_bucket()
        self.client.upload_file(str(path), self.bucket, key)

    def ready(self):
        self.client.list_buckets()
