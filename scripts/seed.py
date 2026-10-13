#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

AUTH_HOST = os.environ.get("FIREBASE_AUTH_EMULATOR_HOST", "localhost:9099")
if "://" not in AUTH_HOST:
    BASE_URL = f"http://{AUTH_HOST}"
else:
    BASE_URL = AUTH_HOST

API_HOST = os.environ.get("API_HOST", "http://localhost:8000")
if "://" not in API_HOST:
    API_URL = f"http://{API_HOST}"
else:
    API_URL = API_HOST

EMAIL = "demo@vixenone.app"
PASSWORD = "demo1234"
DISPLAY_NAME = "Priya Sharma"
ROLE = "facilities_manager"


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
    local_id = None
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
                    local_id = signin_data.get("localId")
        except Exception:
            pass

    if id_token:
        # 1. Ensure display name is set in Firebase Auth
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
        except Exception as exc:
            print(f"Warning: could not update displayName in Firebase: {exc}", file=sys.stderr)

        # 2. Seed profile in Postgres
        seeded_in_postgres = False
        try:
            # First, call GET /api/me to trigger get_or_create
            get_req = urllib.request.Request(
                f"{API_URL}/api/me",
                headers={
                    "Authorization": f"Bearer {id_token}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(get_req) as get_resp:
                json.loads(get_resp.read().decode("utf-8"))

            # Then, ensure display_name and role match seed requirements
            put_payload = {
                "display_name": DISPLAY_NAME,
                "role": ROLE,
            }
            put_req = urllib.request.Request(
                f"{API_URL}/api/me",
                data=json.dumps(put_payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {id_token}",
                    "Content-Type": "application/json",
                },
                method="PUT",
            )
            with urllib.request.urlopen(put_req) as put_resp:
                profile_data = json.loads(put_resp.read().decode("utf-8"))
                print(
                    f"Postgres user profile synced via API: {profile_data.get('display_name')} ({profile_data.get('role')})"
                )
                seeded_in_postgres = True
        except Exception as exc:
            print(f"API sync failed ({exc}); falling back to direct database execution...", file=sys.stderr)

        if not seeded_in_postgres and local_id:
            try:
                sql = (
                    "DO $$ DECLARE cid UUID; BEGIN "
                    f"SELECT company_id INTO cid FROM users WHERE firebase_uid = '{local_id}'; "
                    "IF cid IS NULL THEN "
                    "INSERT INTO companies (id, name) VALUES (gen_random_uuid(), NULL) RETURNING id INTO cid; "
                    "INSERT INTO users (id, company_id, firebase_uid, email, display_name, role) "
                    f"VALUES (gen_random_uuid(), cid, '{local_id}', '{EMAIL}', '{DISPLAY_NAME}', '{ROLE}'); "
                    "ELSE "
                    f"UPDATE users SET display_name = '{DISPLAY_NAME}', role = '{ROLE}' WHERE firebase_uid = '{local_id}'; "
                    "END IF; END $$;"
                )
                subprocess.run(
                    ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "vixenone", "-d", "vixenone", "-c", sql],
                    check=True,
                    capture_output=True,
                )
                print(f"Postgres user profile synced via direct SQL fallback for UID: {local_id}")
            except Exception as sql_exc:
                print(f"Warning: direct SQL fallback failed: {sql_exc}", file=sys.stderr)

        # 3. Seed demo dataset (evaluations, criteria, findings, scores, costs)
        print("Seeding full demo dataset (evaluations, criteria, findings, scores, costs)...")
        try:
            subprocess.run(
                [
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    "api",
                    "python",
                    "-c",
                    "import asyncio; from app.services.seed_demo import seed_demo_data; asyncio.run(seed_demo_data())",
                ],
                check=True,
                capture_output=True,
            )
            print("Full demo dataset seeded successfully.")
        except Exception as seed_exc:
            print(f"Warning: could not run api demo seeder: {seed_exc}", file=sys.stderr)

        return 0

    return 1


if __name__ == "__main__":
    sys.exit(seed_demo_user())
