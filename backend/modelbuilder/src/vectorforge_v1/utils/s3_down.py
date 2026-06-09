from __future__ import annotations

import os
from pathlib import Path

import boto3
import requests
from botocore.config import Config
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_PATH = Path.home() / "Downloads" / "enriched_telecom_churn-2.csv"

load_dotenv()
load_dotenv(PROJECT_ROOT / ".env")


def _env(name: str, default: str | None = None, *, required: bool = False) -> str | None:
    value = os.environ.get(name)
    if value == "" or value is None:
        value = default
    if required and not value:
        raise RuntimeError(f"{name} is required. Add it to .env before running the S3 downloader.")
    return value


def _output_path() -> Path:
    return Path(_env("S3_DOWNLOAD_OUTPUT_PATH", str(DEFAULT_OUTPUT_PATH)) or DEFAULT_OUTPUT_PATH).expanduser()


def generate_presigned_url() -> str:
    s3_client = boto3.client(
        "s3",
        region_name=_env("AWS_REGION", "us-west-2"),
        aws_access_key_id=_env("AWS_ACCESS_KEY_ID", required=True),
        aws_secret_access_key=_env("AWS_SECRET_ACCESS_KEY", required=True),
        aws_session_token=_env("AWS_SESSION_TOKEN"),
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"},
        ),
    )

    return s3_client.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": _env("S3_DOWNLOAD_BUCKET_NAME", required=True),
            "Key": _env("S3_DOWNLOAD_OBJECT_KEY", required=True),
        },
        ExpiresIn=int(_env("S3_DOWNLOAD_EXPIRES_IN", "3600") or "3600"),
    )


def download_file(url: str, output_path: Path | None = None) -> Path:
    destination = output_path or _output_path()
    destination.parent.mkdir(parents=True, exist_ok=True)

    print("Presigned URL:")
    print(url)

    response = requests.get(url, timeout=120)

    print("Download status:", response.status_code)
    print("Content-Type:", response.headers.get("Content-Type"))

    if response.status_code != 200:
        print("Response preview:")
        print(response.text[:1000])

    response.raise_for_status()
    destination.write_bytes(response.content)

    print(f"Downloaded successfully: {destination}")
    print(f"Size: {destination.stat().st_size:,} bytes")
    return destination


def test_download_csv_with_presigned_url() -> Path:
    presigned_url = generate_presigned_url()
    return download_file(presigned_url)


if __name__ == "__main__":
    test_download_csv_with_presigned_url()
