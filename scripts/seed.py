#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request

AUTH_HOST = os.environ.get("FIREBASE_AUTH_EMULATOR_HOST", "localhost:9099")
if "://" not in AUTH_HOST:
    BASE_URL = f"http://{AUTH_HOST}"
else:
    BASE_URL = AUTH_HOST

EMAIL = "demo@vixenone.app"
PASSWORD = "demo1234"
DISPLAY_NAME = "Priya Sharma"


def seed_demo_user():
    print(f"Connecting to Firebase Auth emulator at {BASE_URL}...")
    signup_url = f"{BASE_URL}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=fake-api-key"
    payload = {
        "email": EMAIL,
        "password": PASSWORD,
        "displayName": DISPLAY_NAME,
        "returnSecureToken": True,
    }

    id_token = None
    try:
        req = urllib.request.Request(
            signup_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            local_id = data.get("localId", "unknown")
            id_token = data.get("idToken")
            print(f"Created demo user '{EMAIL}' (UID: {local_id}).")
    except urllib.error.HTTPError as err:
        err_body = err.read().decode("utf-8")
        try:
            err_data = json.loads(err_body)
            msg = err_data.get("error", {}).get("message", "")
            if "EMAIL_EXISTS" in msg:
                print(f"Demo user '{EMAIL}' exists. Refreshing session...")
                signin_url = f"{BASE_URL}/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=fake-api-key"
                signin_payload = {
                    "email": EMAIL,
                    "password": PASSWORD,
                    "returnSecureToken": True,
                }
                signin_req = urllib.request.Request(
                    signin_url,
                    data=json.dumps(signin_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(signin_req) as signin_resp:
                    signin_data = json.loads(signin_resp.read().decode("utf-8"))
                    id_token = signin_data.get("idToken")
        except Exception:
            pass

    if id_token:
        # Ensure display name is set
        update_url = f"{BASE_URL}/identitytoolkit.googleapis.com/v1/accounts:update?key=fake-api-key"
        update_payload = {
            "idToken": id_token,
            "displayName": DISPLAY_NAME,
            "returnSecureToken": True,
        }
        update_req = urllib.request.Request(
            update_url,
            data=json.dumps(update_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(update_req) as update_resp:
                update_data = json.loads(update_resp.read().decode("utf-8"))
                print(f"Demo user '{EMAIL}' verified with Display Name: {update_data.get('displayName')}")
                return 0
        except Exception as exc:
            print(f"Warning: could not update displayName: {exc}", file=sys.stderr)
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(seed_demo_user())
