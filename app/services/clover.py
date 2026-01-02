import os
import requests
import asyncio
from typing import Tuple, Dict, Any, Optional
from app.core.logging import get_logger
from app.utils.crypto_utils import decrypt_value

logger = get_logger(__name__)

# Clover API configuration (sandbox by default)
CLOVER_APP_ID = os.getenv("CLOVER_APP_ID")
CLOVER_APP_SECRET = os.getenv("CLOVER_APP_SECRET")
CLOVER_BASE_API = os.getenv("CLOVER_BASE_API", "https://apisandbox.dev.clover.com")
CLOVER_OAUTH_URL = os.getenv("CLOVER_OAUTH_URL", "https://sandbox.dev.clover.com/oauth/authorize")
CLOVER_TOKEN_URL = os.getenv("CLOVER_TOKEN_URL", "https://sandbox.dev.clover.com/oauth/token")

# In-memory token storage for demo; production should persist tokens securely
clover_tokens: Dict[str, Dict[str, Any]] = {}


def get_clover_auth_url(merchant_id: str) -> str:
    if not CLOVER_APP_ID:
        raise ValueError("CLOVER_APP_ID not set")
    return f"{CLOVER_OAUTH_URL}?client_id={CLOVER_APP_ID}&response_type=code&merchant_id={merchant_id}"


def exchange_code_for_token(code: str, merchant_id: str) -> Dict[str, Any]:
    if not CLOVER_APP_ID or not CLOVER_APP_SECRET:
        raise ValueError("CLOVER_APP_ID and CLOVER_APP_SECRET not set")
    data = {
        "client_id": CLOVER_APP_ID,
        "client_secret": CLOVER_APP_SECRET,
        "code": code,
        "grant_type": "authorization_code"
    }
    resp = requests.post(CLOVER_TOKEN_URL, data=data)
    if resp.status_code != 200:
        raise ValueError(f"Failed to get token: {resp.text}")
    token_data = resp.json()
    clover_tokens[merchant_id] = token_data
    return token_data


def refresh_access_token(merchant_id: str) -> Optional[str]:
    if merchant_id not in clover_tokens:
        return None
    token_data = clover_tokens[merchant_id]
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        return None
    data = {
        "client_id": CLOVER_APP_ID,
        "client_secret": CLOVER_APP_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }
    resp = requests.post(CLOVER_TOKEN_URL, data=data)
    if resp.status_code != 200:
        return None
    new_token_data = resp.json()
    clover_tokens[merchant_id] = new_token_data
    return new_token_data.get("access_token")


def _sync_request(method: str, url: str, headers: dict, payload: Optional[dict], params: Optional[dict]):
    return requests.request(method, url, headers=headers, json=payload, params=params)


async def proxy_to_clover(method: str, url: str, access_token: str, merchant_id: str, payload: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict[str, Any]:
    # ensure access_token is decrypted if stored encrypted
    access_token = decrypt_value(access_token)
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    def _call():
        logger.debug(f"[CLOVER] Request: {method} {url} params={params} payload={payload}")
        return requests.request(method, url, headers=headers, json=payload, params=params)

    resp = await asyncio.to_thread(_call)
    logger.debug(f"[CLOVER] Response status: {resp.status_code}")
    if resp.status_code == 401:
        new_token = refresh_access_token(merchant_id)
        if new_token:
            headers["Authorization"] = f"Bearer {new_token}"
            resp = await asyncio.to_thread(_call)
            if resp.status_code < 400:
                clover_tokens[merchant_id]["access_token"] = new_token
                return resp.json()
        raise ValueError(f"Clover API error: 401 Unauthorized: {resp.text}")
    if resp.status_code >= 400:
        raise ValueError(f"Clover API error: {resp.status_code} {resp.text}")
    return resp.json()
