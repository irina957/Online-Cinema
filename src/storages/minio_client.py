import io
import json

from minio import Minio
from minio.error import S3Error
from src.config.settings import settings

minio_client = Minio(
    "minio:9000",
    access_key=settings.MINIO_ROOT_USER,
    secret_key=settings.MINIO_ROOT_PASSWORD,
    secure=False,
)

BUCKET_NAME = "cinema-avatars"


def ensure_bucket_exists() -> None:
    if not minio_client.bucket_exists(BUCKET_NAME):
        minio_client.make_bucket(BUCKET_NAME)

    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": "*"},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{BUCKET_NAME}/*"],
            }
        ],
    }
    minio_client.set_bucket_policy(BUCKET_NAME, json.dumps(policy))


def upload_avatar(file_data: bytes, filename: str, content_type: str) -> str:
    ensure_bucket_exists()
    minio_client.put_object(
        BUCKET_NAME,
        filename,
        io.BytesIO(file_data),
        length=len(file_data),
        content_type=content_type,
    )
    return filename


def delete_avatar(filename: str) -> None:
    try:
        minio_client.remove_object(BUCKET_NAME, filename)
    except S3Error:
        pass


minio_client_public = Minio(
    "localhost:9000",
    access_key=settings.MINIO_ROOT_USER,
    secret_key=settings.MINIO_ROOT_PASSWORD,
    secure=False,
)


def get_avatar_url(filename: str) -> str:
    return f"http://localhost:9000/{BUCKET_NAME}/{filename}"
