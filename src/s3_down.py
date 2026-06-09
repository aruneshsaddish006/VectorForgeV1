from pathlib import Path
import boto3
import requests
from botocore.config import Config

# ===== CONFIG =====
AWS_ACCESS_KEY_ID = "AKIA5BXDK6TMC5BEBHGX"
AWS_SECRET_ACCESS_KEY = "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"
AWS_SESSION_TOKEN = None
AWS_REGION = "us-west-2"

BUCKET_NAME = "vector-forge-s3"
OBJECT_KEY = "datasets/enriched_telecom_churn-2.csv"

OUTPUT_PATH = Path.home() / "Downloads" / "enriched_telecom_churn-2.csv"
# ==================


def generate_presigned_url() -> str:
    s3_client = boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        aws_session_token=AWS_SESSION_TOKEN,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"},
        ),
    )

    return s3_client.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": BUCKET_NAME,
            "Key": OBJECT_KEY,
        },
        ExpiresIn=3600,  # 1 hour
    )


def download_file(url: str):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print("Presigned URL:")
    print(url)

    response = requests.get(url, timeout=120)

    print("Download status:", response.status_code)
    print("Content-Type:", response.headers.get("Content-Type"))

    if response.status_code != 200:
        print("Response preview:")
        print(response.text[:1000])

    response.raise_for_status()

    OUTPUT_PATH.write_bytes(response.content)

    print(f"Downloaded successfully: {OUTPUT_PATH}")
    print(f"Size: {OUTPUT_PATH.stat().st_size:,} bytes")


def test_download_csv_with_presigned_url():
    presigned_url = generate_presigned_url()
    download_file(presigned_url)


if __name__ == "__main__":
    test_download_csv_with_presigned_url()
