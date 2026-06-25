"""Helpers for Dropbox authentication.

This module hides the environment-variable and token-refresh details used to get
an access token before any Dropbox API call is made.
"""

import base64
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OAUTH_TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"


def require_access_token() -> str:
    """Return a Dropbox access token from env vars or refresh credentials."""
    direct_token = os.environ.get("DROPBOX_ACCESS_TOKEN")
    if direct_token:
        return direct_token

    refresh_token = os.environ.get("DROPBOX_REFRESH_TOKEN")
    app_key = os.environ.get("DROPBOX_APP_KEY")
    app_secret = os.environ.get("DROPBOX_APP_SECRET")

    if not refresh_token or not app_key or not app_secret:
        raise RuntimeError(
            "Provide DROPBOX_ACCESS_TOKEN or the trio of DROPBOX_REFRESH_TOKEN, "
            "DROPBOX_APP_KEY, and DROPBOX_APP_SECRET."
        )

    credentials = base64.b64encode(f"{app_key}:{app_secret}".encode("utf-8")).decode(
        "ascii"
    )
    request = Request(
        OAUTH_TOKEN_URL,
        data=urlencode(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
        ).encode("utf-8"),
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    with urlopen(request) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload["access_token"]
