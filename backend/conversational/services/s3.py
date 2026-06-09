"""S3 file upload service for VectorForge dataset storage.

Credentials and bucket are read from .env via config.get_settings().

Upload pattern (interrupt/resume):
1. Graph interrupts asking user to choose a dataset source
2. User picks "upload" — API receives file on POST /conversations/{id}/upload-dataset
3. upload_dataset() uploads bytes to S3 and returns the s3_path
4. API resumes graph: Command(resume={choice: "upload", s3_path: "s3://..."})
"""

from __future__ import annotations

import io

import boto3
from botocore.exceptions import ClientError

from conversational.config import get_settings


def _get_s3_client():
    cfg = get_settings()
    kwargs: dict = {
        "aws_access_key_id": cfg.aws_access_key,
        "aws_secret_access_key": cfg.aws_secret_access_key,
        "region_name": cfg.aws_default_region,
    }
    if cfg.aws_session_token:
        kwargs["aws_session_token"] = cfg.aws_session_token
    return boto3.client("s3", **kwargs)


async def upload_dataset(
    session_id: str,
    prob_id: str,
    filename: str,
    data: bytes,
    content_type: str = "text/csv",
) -> str:
    """Upload a dataset file to S3 and return the s3:// URI.

    S3 key: {session_id}/{prob_id}/{filename}

    Returns:
        "s3://{bucket}/{session_id}/{prob_id}/{filename}"
    """
    bucket = get_settings().s3_bucket_name
    key = f"{session_id}/{prob_id}/{filename}"

    s3 = _get_s3_client()
    s3.upload_fileobj(
        io.BytesIO(data),
        bucket,
        key,
        ExtraArgs={"ContentType": content_type},
    )

    return f"s3://{bucket}/{key}"


async def upload_autorag_files(
    session_id: str,
    prob_id: str,
    corpus_data: bytes,
    qa_data: bytes | None = None,
) -> dict[str, str]:
    """Upload AutoRAG corpus and optional QA eval file.

    Returns dict with "corpus_s3_path" and optionally "qa_s3_path".
    """
    result: dict[str, str] = {}
    result["corpus_s3_path"] = await upload_dataset(
        session_id, prob_id, "corpus.csv", corpus_data
    )
    if qa_data is not None:
        result["qa_s3_path"] = await upload_dataset(
            session_id, prob_id, "qa_eval.csv", qa_data
        )
    return result


def generate_presigned_url(s3_path: str, expiry_seconds: int = 3600) -> str:
    """Generate a presigned download URL for an S3 object."""
    if not s3_path.startswith("s3://"):
        raise ValueError(f"Invalid s3_path: {s3_path}")
    parts = s3_path[5:].split("/", 1)
    bucket, key = parts[0], parts[1]
    return _get_s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expiry_seconds,
    )


def bucket_exists() -> bool:
    """Return True if the configured S3 bucket is accessible."""
    try:
        _get_s3_client().head_bucket(Bucket=get_settings().s3_bucket_name)
        return True
    except ClientError:
        return False
