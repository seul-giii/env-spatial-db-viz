import boto3
import os


class S3Uploader:
    def __init__(self):
        # 환경 변수에서 AWS 인증 정보를 가져옴
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name='ap-northeast-2'
        )
        self.bucket_name = os.getenv('AWS_S3_BUCKET', '버킷-이름')

    def upload_bytes(self, file_bytes: bytes, file_name: str) -> str:
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=file_name,
            Body=file_bytes
        )

        # 업로드된 파일의 S3 URL 생성
        url = f"https://{self.bucket_name}.s3.ap-northeast-2.amazonaws.com/{file_name}"
        return url