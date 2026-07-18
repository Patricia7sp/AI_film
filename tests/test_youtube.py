import os
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.integration
YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"


def _youtube_service() -> Any:
    credentials_module = pytest.importorskip("google.oauth2.credentials")
    discovery_module = pytest.importorskip("googleapiclient.discovery")
    token_value = os.getenv("YOUTUBE_TOKEN_FILE", "").strip()
    if not token_value:
        pytest.skip("YOUTUBE_TOKEN_FILE is not configured")
    token_path = Path(token_value).expanduser().resolve()
    if not token_path.is_file():
        pytest.fail(f"YOUTUBE_TOKEN_FILE does not exist: {token_path}")

    credentials = credentials_module.Credentials.from_authorized_user_file(
        str(token_path), [YOUTUBE_UPLOAD_SCOPE]
    )
    assert credentials.valid or credentials.refresh_token
    return discovery_module.build("youtube", "v3", credentials=credentials)


def test_youtube_initialization() -> None:
    youtube = _youtube_service()
    response = (
        youtube.channels().list(part="snippet", mine=True, maxResults=1).execute()
    )
    assert "items" in response


@pytest.mark.destructive
def test_upload_private_video() -> None:
    if os.getenv("RUN_YOUTUBE_UPLOAD_TESTS", "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }:
        pytest.skip("set RUN_YOUTUBE_UPLOAD_TESTS=1 to authorize a private upload")

    media_module = pytest.importorskip("googleapiclient.http")
    video_value = os.getenv("YOUTUBE_TEST_VIDEO_PATH", "").strip()
    if not video_value:
        pytest.skip("YOUTUBE_TEST_VIDEO_PATH is not configured")
    video_path = Path(video_value).expanduser().resolve()
    if not video_path.is_file():
        pytest.fail(f"YOUTUBE_TEST_VIDEO_PATH does not exist: {video_path}")

    response = (
        _youtube_service()
        .videos()
        .insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": "AI Film integration test",
                    "description": "Automated private integration test upload.",
                    "categoryId": "1",
                },
                "status": {
                    "privacyStatus": "private",
                    "selfDeclaredMadeForKids": False,
                },
            },
            media_body=media_module.MediaFileUpload(
                str(video_path), mimetype="video/mp4", resumable=True
            ),
        )
        .execute()
    )
    assert response.get("id")
