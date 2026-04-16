"""Google Cloud authentication for BigQuery — credential factory and helpful error messages."""

from __future__ import annotations

import asyncio
import sys

from google.auth.exceptions import DefaultCredentialsError
from google.cloud import bigquery


def get_helpful_auth_error(error: Exception) -> str:
    """Convert a BigQuery / GCloud exception into an actionable error message."""
    error_str = str(error).lower()

    if isinstance(error, DefaultCredentialsError):
        return (
            "No Google Cloud credentials found. Please authenticate using one of:\n"
            "  1. gcloud auth application-default login\n"
            "  2. Set GOOGLE_APPLICATION_CREDENTIALS to your service account JSON file path\n"
            "  3. Use a service account in a GCP environment (Compute Engine, Cloud Run, etc.)"
        )

    if "permission denied" in error_str or "forbidden" in error_str:
        return (
            f"Permission denied: {error}\n"
            "Ensure your credentials have the following BigQuery IAM roles:\n"
            "  - BigQuery Data Viewer   (read dataset metadata and tables)\n"
            "  - BigQuery Job User      (run queries)\n"
            "  - BigQuery User          (general BigQuery access)\n"
            "  - BigQuery Metadata Viewer  (optional — required for vector search discovery)"
        )

    if "quota exceeded" in error_str:
        return (
            f"BigQuery quota exceeded: {error}\n"
            "Check your project's BigQuery quotas and billing settings:\n"
            "  https://console.cloud.google.com/iam-admin/quotas"
        )

    if "project" in error_str and ("not found" in error_str or "invalid" in error_str):
        import os
        return (
            f"Project access issue: {error}\n"
            "Verify:\n"
            f"  - BIGQUERY_PROJECT_ID is correct: {os.getenv('BIGQUERY_PROJECT_ID')}\n"
            "  - Your credentials have access to this project\n"
            "  - The BigQuery API is enabled: "
            "https://console.cloud.google.com/apis/library/bigquery.googleapis.com"
        )

    if "location" in error_str:
        import os
        return (
            f"BigQuery location issue: {error}\n"
            f"Verify BIGQUERY_LOCATION is correct: {os.getenv('BIGQUERY_LOCATION')}\n"
            "Common values: US, EU, us-central1, europe-west4"
        )

    return (
        f"Authentication failed: {error}\n"
        "Common fixes:\n"
        "  1. gcloud auth application-default login\n"
        "  2. Verify BIGQUERY_PROJECT_ID environment variable\n"
        "  3. Ensure the BigQuery API is enabled in your project\n"
        "  4. Confirm your account has BigQuery IAM roles"
    )


async def validate_authentication(
    bigquery_client: bigquery.Client,
    project_id: str,
    location: str | None = None,
) -> None:
    """Validate GCP credentials and BigQuery permissions on server startup.

    Performs two lightweight checks:
      1. Lists at most 1 dataset (tests Data Viewer + project access).
      2. Runs a dry-run SELECT 1 query (tests Job User permissions).

    Raises SystemExit(1) with a human-readable message on failure.
    """
    print(f"[bigquery] Validating credentials for project: {project_id}")
    if location:
        print(f"[bigquery] Location: {location}")

    # Step 1 — dataset list (tests project access + Data Viewer role)
    try:
        await asyncio.to_thread(lambda: list(bigquery_client.list_datasets(max_results=1)))
    except Exception as err:
        print(f"[bigquery] ❌ Authentication failed:\n{get_helpful_auth_error(err)}")
        sys.exit(1)

    # Step 2 — dry-run query (tests Job User role)
    try:
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        await asyncio.to_thread(
            lambda: bigquery_client.query("SELECT 1 AS test_column", job_config=job_config)
        )
    except Exception as err:
        print(f"[bigquery] ❌ Query permission check failed:\n{get_helpful_auth_error(err)}")
        sys.exit(1)

    print("[bigquery] ✅ Credentials and permissions validated")


def create_bigquery_client(
    project_id: str,
    location: str | None = None,
    key_file: str | None = None,
) -> bigquery.Client:
    """Create and return a BigQuery client.

    Auth priority:
      1. key_file path (service account JSON)
      2. GOOGLE_APPLICATION_CREDENTIALS env var (already picked up by google-auth)
      3. Application Default Credentials
    """
    kwargs: dict = {"project": project_id}
    if location:
        kwargs["location"] = location

    if key_file:
        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_file(
            key_file,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        kwargs["credentials"] = credentials

    return bigquery.Client(**kwargs)
