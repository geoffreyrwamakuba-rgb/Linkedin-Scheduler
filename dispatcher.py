"""LinkedIn post dispatcher — runs on GitHub Actions.

Reads queue.json; any pending item whose scheduled time (Europe/London) has
passed is published to LinkedIn via the official Share on LinkedIn API.
Statuses are written back to queue.json (the workflow commits the change).

Env (from repo secrets):
  LINKEDIN_ACCESS_TOKEN, LINKEDIN_MEMBER_URN

Queue item shape:
  { "when": "2026-07-28T11:00", "text_file": "posts/foo.txt",
    "image": "images/bar.png" (optional), "label": "short name",
    "status": "pending" }
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent
QUEUE_PATH = ROOT / "queue.json"
LONDON = ZoneInfo("Europe/London")
GRACE_HOURS = 48
API = "https://api.linkedin.com/v2"

TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
MEMBER_URN = os.environ.get("LINKEDIN_MEMBER_URN", "")
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "X-Restli-Protocol-Version": "2.0.0",
    "Content-Type": "application/json",
}


def upload_image(image_path: Path) -> str:
    register = requests.post(
        f"{API}/assets?action=registerUpload",
        headers=HEADERS,
        json={
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": MEMBER_URN,
                "serviceRelationships": [
                    {"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}
                ],
            }
        },
        timeout=30,
    )
    register.raise_for_status()
    data = register.json()["value"]
    upload_url = data["uploadMechanism"][
        "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
    ]["uploadUrl"]
    with open(image_path, "rb") as f:
        requests.put(upload_url, data=f.read(),
                     headers={"Authorization": f"Bearer {TOKEN}"}, timeout=120).raise_for_status()
    return data["asset"]


def create_post(text: str, asset_urn: str | None) -> str:
    media = (
        {"shareMediaCategory": "IMAGE", "media": [{"status": "READY", "media": asset_urn}]}
        if asset_urn
        else {"shareMediaCategory": "NONE"}
    )
    body = {
        "author": MEMBER_URN,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {"shareCommentary": {"text": text}, **media}
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    resp = requests.post(f"{API}/ugcPosts", headers=HEADERS, json=body, timeout=30)
    if resp.status_code >= 400:
        raise RuntimeError(f"Post failed ({resp.status_code}): {resp.text}")
    return resp.headers.get("X-RestLi-Id", "unknown")


def main():
    if not TOKEN or not MEMBER_URN:
        sys.exit("LINKEDIN_ACCESS_TOKEN / LINKEDIN_MEMBER_URN secrets not set.")

    data = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    now = datetime.now(LONDON)
    changed = False

    for item in data.get("queue", []):
        if item.get("status") != "pending":
            continue
        due = datetime.fromisoformat(item["when"]).replace(tzinfo=LONDON)
        if now < due:
            continue
        label = item.get("label", item.get("text_file", "?"))
        hours_late = (now - due).total_seconds() / 3600
        if hours_late > GRACE_HOURS:
            item["status"] = "missed"
            changed = True
            print(f"MISSED (> {GRACE_HOURS}h late): {label}")
            continue
        try:
            text = (ROOT / item["text_file"]).read_text(encoding="utf-8").strip()
            if not text or len(text) > 3000:
                raise RuntimeError(f"text empty or over 3000 chars ({len(text)})")
            asset = upload_image(ROOT / item["image"]) if item.get("image") else None
            post_id = create_post(text, asset)
            item["status"] = "posted"
            item["posted_at"] = now.isoformat(timespec="seconds")
            item["post_id"] = post_id
            print(f"POSTED: {label} — {post_id}")
        except Exception as e:  # noqa: BLE001 — one bad item must not block the rest
            item["status"] = "failed"
            item["error"] = str(e)[:500]
            print(f"FAILED: {label} — {e}")
        changed = True
        time.sleep(5)

    if changed:
        QUEUE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("queue.json updated")

    # Token-expiry heads-up in the Actions log
    expires = data.get("token_expires")
    if expires:
        days = (datetime.fromisoformat(expires).replace(tzinfo=LONDON) - now).days
        if days <= 7:
            print(f"::warning::LinkedIn token expires in {days} days — re-run tools/linkedin_auth.py locally and update the LINKEDIN_ACCESS_TOKEN secret.")


if __name__ == "__main__":
    main()
