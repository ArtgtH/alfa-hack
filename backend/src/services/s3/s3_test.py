from db.models import User


async def upload_to_s3(file: bytes, filename: str, user: User):
    return "test_minio_url"
