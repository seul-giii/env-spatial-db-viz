import os
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
    config=Config(
        signature_version='s3v4',
        s3={'addressing_style': 'virtual'}
    )
)


def upload_to_s3(local_file_path: str, object_name: str = None, prefix: str = "exports") -> str:
    """파일을 S3에 업로드하고 S3 키를 반환합니다."""
    if not S3_BUCKET_NAME:
        raise ValueError("S3_BUCKET_NAME 환경 변수가 설정되지 않았습니다.")

    if object_name is None:
        object_name = os.path.basename(local_file_path)

    s3_key = f"{prefix}/{object_name}"

    try:
        s3_client.upload_file(local_file_path, S3_BUCKET_NAME, s3_key)
        return s3_key
    except ClientError as e:
        print(f"❌ S3 업로드 중 에러 발생: {e}")
        raise RuntimeError(f"S3 전송 실패: {e}") from e
    except Exception as e:
        print(f"❌ 알 수 없는 에러 발생: {e}")
        raise RuntimeError(f"업로드 처리 중 오류: {e}") from e


def generate_presigned_url(s3_key: str, expires_in: int = 3600) -> str:
    """S3 키로부터 다운로드용 Presigned URL을 생성합니다."""
    if not S3_BUCKET_NAME:
        raise ValueError("S3_BUCKET_NAME 환경 변수가 설정되지 않았습니다.")

    try:
        return s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=expires_in
        )
    except ClientError as e:
        print(f"❌ Presigned URL 생성 중 에러 발생: {e}")
        raise RuntimeError(f"Presigned URL 생성 실패: {e}") from e