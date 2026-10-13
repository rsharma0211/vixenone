import asyncio
from unittest.mock import patch
import uuid
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.core.database import async_session
from app.main import app
from app.models.company import Company, Location
from app.models.user import User
from app.schemas.evaluation import EvaluationCreate
from app.services.seed_demo import DEMO_EMAIL, seed_demo_data

client = TestClient(app)


def fake_token(uid: str, email: str = "user@vixenone.app", name: str = "Test User"):
    return {"uid": uid, "email": email, "name": name}


def test_free_text_location_field_removed_from_evaluation_create_schema():
    assert "location" not in EvaluationCreate.model_fields
    assert "location_id" in EvaluationCreate.model_fields


def test_migration_backfill_gives_every_existing_user_a_company():
    from app.core.database import engine

    async def verify_backfill():
        # 1. Verify all existing users in DB have a non-null company_id pointing to a valid Company
        async with async_session() as s:
            users = list((await s.execute(select(User))).scalars().all())
            for u in users:
                assert u.company_id is not None
                comp = await s.get(Company, u.company_id)
                assert comp is not None

        # 2. Simulate pre-backfill state inside a rolled-back transaction and run the migration 0005 backfill SQL
        backfill_sql = """
        DO $$
        DECLARE
            u RECORD;
            new_cid UUID;
        BEGIN
            FOR u IN SELECT id FROM users WHERE company_id IS NULL LOOP
                INSERT INTO companies (id, name, created_at, updated_at)
                VALUES (gen_random_uuid(), NULL, now(), now())
                RETURNING id INTO new_cid;
                UPDATE users SET company_id = new_cid WHERE id = u.id;
            END LOOP;
        END $$;
        """
        async with engine.connect() as conn:
            trans = await conn.begin()
            try:
                await conn.execute(text("ALTER TABLE users ALTER COLUMN company_id DROP NOT NULL"))
                temp_uid = f"uid-backfill-{uuid.uuid4().hex}"
                temp_user_id = uuid.uuid4()
                await conn.execute(
                    text(
                        "INSERT INTO users (id, company_id, firebase_uid, email, display_name, role) "
                        "VALUES (:id, NULL, :uid, 'backfill@vixenone.app', 'Backfill User', 'facilities_manager')"
                    ),
                    {"id": temp_user_id, "uid": temp_uid},
                )
                await conn.execute(text(backfill_sql))
                await conn.execute(text("ALTER TABLE users ALTER COLUMN company_id SET NOT NULL"))

                row = (
                    await conn.execute(
                        text("SELECT company_id FROM users WHERE id = :id"),
                        {"id": temp_user_id},
                    )
                ).first()
                assert row is not None and row[0] is not None
                comp_row = (
                    await conn.execute(
                        text("SELECT id, name FROM companies WHERE id = :cid"),
                        {"cid": row[0]},
                    )
                ).first()
                assert comp_row is not None
                assert comp_row[1] is None
            finally:
                await trans.rollback()

    asyncio.run(verify_backfill())


def test_new_profile_gets_company_on_me():
    uid = f"uid-new-profile-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid, "newp@vixenone.app")):
        res = client.get("/api/me", headers={"Authorization": "Bearer token"})
        assert res.status_code == 200
        user_id = uuid.UUID(res.json()["id"])

        comp_res = client.get("/api/company", headers={"Authorization": "Bearer token"})
        assert comp_res.status_code == 200
        comp_data = comp_res.json()
        assert comp_data["name"] is None
        assert comp_data["locations"] == []

    async def check_db():
        async with async_session() as s:
            u = await s.get(User, user_id)
            assert u is not None
            assert str(u.company_id) == comp_data["id"]

    asyncio.run(check_db())


@pytest.mark.asyncio
async def test_get_company_read_or_create_and_concurrency():
    uid = f"uid-comp-direct-{uuid.uuid4().hex}"
    token = fake_token(uid, "compdirect@vixenone.app", "Direct User")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("firebase_admin.auth.verify_id_token", return_value=token):
            r1, r2 = await asyncio.gather(
                ac.get("/api/company", headers={"Authorization": "Bearer token"}),
                ac.get("/api/company", headers={"Authorization": "Bearer token"}),
            )
            assert r1.status_code == 200
            assert r2.status_code == 200
            assert r1.json()["id"] == r2.json()["id"]
            assert r1.json()["name"] is None
            assert r1.json()["locations"] == []


def test_company_name_trim_empty_to_null_and_length_validation():
    uid = f"uid-comp-patch-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        auth = {"Authorization": "Bearer token"}

        # Trim valid name
        r1 = client.patch("/api/company", headers=auth, json={"name": "  Northbridge Holdings  "})
        assert r1.status_code == 200
        assert r1.json()["name"] == "Northbridge Holdings"

        # Empty string -> stored as null
        r2 = client.patch("/api/company", headers=auth, json={"name": ""})
        assert r2.status_code == 200
        assert r2.json()["name"] is None

        # Whitespace-only string -> stored as null
        r3 = client.patch("/api/company", headers=auth, json={"name": "    "})
        assert r3.status_code == 200
        assert r3.json()["name"] is None

        # > 120 characters after trim -> 422
        r4 = client.patch("/api/company", headers=auth, json={"name": "A" * 121})
        assert r4.status_code == 422

        # Exactly 120 characters -> 200
        r5 = client.patch("/api/company", headers=auth, json={"name": "B" * 120})
        assert r5.status_code == 200
        assert r5.json()["name"] == "B" * 120


def test_location_crud_validation_positions_and_delete_constraints():
    uid = f"uid-loc-crud-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        auth = {"Authorization": "Bearer token"}

        # Empty name or city -> 422
        assert client.post("/api/company/locations", headers=auth, json={"name": "", "city": "Mumbai"}).status_code == 422
        assert client.post("/api/company/locations", headers=auth, json={"name": "   ", "city": "Mumbai"}).status_code == 422
        assert client.post("/api/company/locations", headers=auth, json={"name": "Office", "city": ""}).status_code == 422
        assert client.post("/api/company/locations", headers=auth, json={"name": "Office", "city": "   "}).status_code == 422
        assert client.post("/api/company/locations", headers=auth, json={"name": "X" * 81, "city": "Mumbai"}).status_code == 422
        assert client.post("/api/company/locations", headers=auth, json={"name": "Office", "city": "Y" * 81}).status_code == 422

        # Add 3 locations -> appended at positions 0, 1, 2
        l1 = client.post("/api/company/locations", headers=auth, json={"name": "  Andheri East  ", "city": "  Mumbai  "})
        assert l1.status_code == 201
        assert l1.json()["name"] == "Andheri East"
        assert l1.json()["city"] == "Mumbai"
        assert l1.json()["position"] == 0
        assert l1.json()["evaluation_count"] == 0
        l1_id = l1.json()["id"]

        l2 = client.post("/api/company/locations", headers=auth, json={"name": "Powai Campus", "city": "Mumbai"})
        assert l2.status_code == 201
        assert l2.json()["position"] == 1
        l2_id = l2.json()["id"]

        l3 = client.post("/api/company/locations", headers=auth, json={"name": "Thane Warehouse", "city": "Thane"})
        assert l3.status_code == 201
        assert l3.json()["position"] == 2
        l3_id = l3.json()["id"]

        # Duplicate name (case-insensitive) -> 422
        dup = client.post("/api/company/locations", headers=auth, json={"name": "andheri east", "city": "Pune"})
        assert dup.status_code == 422

        # Rename location & update city
        ren = client.patch(f"/api/company/locations/{l2_id}", headers=auth, json={"name": "  Powai Tech Park  ", "city": "  Navi Mumbai  "})
        assert ren.status_code == 200
        assert ren.json()["name"] == "Powai Tech Park"
        assert ren.json()["city"] == "Navi Mumbai"
        assert ren.json()["position"] == 1

        # Rename to duplicate (case-insensitive) of another location -> 422
        ren_dup = client.patch(f"/api/company/locations/{l2_id}", headers=auth, json={"name": "ANDHERI EAST"})
        assert ren_dup.status_code == 422

        # Rename with empty name or city -> 422
        assert client.patch(f"/api/company/locations/{l2_id}", headers=auth, json={"name": "  "}).status_code == 422
        assert client.patch(f"/api/company/locations/{l2_id}", headers=auth, json={"city": ""}).status_code == 422

        # Delete unused middle location (l2) -> 204 and positions re-numbered without gaps (0, 1)
        del_unused = client.delete(f"/api/company/locations/{l2_id}", headers=auth)
        assert del_unused.status_code == 204

        comp = client.get("/api/company", headers=auth).json()
        assert [loc["id"] for loc in comp["locations"]] == [l1_id, l3_id]
        assert [loc["position"] for loc in comp["locations"]] == [0, 1]

        # Link 2 evaluations to l1_id
        ev1 = client.post(
            "/api/evaluations",
            headers=auth,
            json={"title": "Eval 1", "category": "Facilities", "location_id": l1_id},
        )
        assert ev1.status_code == 201
        ev2 = client.post(
            "/api/evaluations",
            headers=auth,
            json={"title": "Eval 2", "category": "Facilities", "location_id": l1_id},
        )
        assert ev2.status_code == 201

        # Check evaluation_count on GET /api/company
        comp_after = client.get("/api/company", headers=auth).json()
        loc_map = {loc["id"]: loc for loc in comp_after["locations"]}
        assert loc_map[l1_id]["evaluation_count"] == 2
        assert loc_map[l3_id]["evaluation_count"] == 0

        # Delete used location -> 409 "Used by 2 evaluations."
        del_used = client.delete(f"/api/company/locations/{l1_id}", headers=auth)
        assert del_used.status_code == 409
        assert del_used.json()["detail"] == "Used by 2 evaluations."


def test_evaluation_location_create_patch_clear_and_cross_company_isolation():
    uid1 = f"uid-comp1-{uuid.uuid4().hex}"
    uid2 = f"uid-comp2-{uuid.uuid4().hex}"

    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid1, "u1@vixenone.app")):
        auth1 = {"Authorization": "Bearer token1"}
        loc1 = client.post(
            "/api/company/locations",
            headers=auth1,
            json={"name": "BKC Office", "city": "Mumbai"},
        ).json()
        loc1_id = loc1["id"]

        loc1_b = client.post(
            "/api/company/locations",
            headers=auth1,
            json={"name": "Worli Annex", "city": "Mumbai"},
        ).json()
        loc1_b_id = loc1_b["id"]

        # Create evaluation with own location -> 201, detail includes location {id, name, city}
        ev_res = client.post(
            "/api/evaluations",
            headers=auth1,
            json={"title": "Housekeeping BKC", "category": "Housekeeping", "location_id": loc1_id},
        )
        assert ev_res.status_code == 201
        ev_detail = ev_res.json()
        ev_id = ev_detail["id"]
        assert ev_detail["location"] == {"id": loc1_id, "name": "BKC Office", "city": "Mumbai"}

        # List response also includes location {id, name, city}
        list_res = client.get("/api/evaluations", headers=auth1).json()
        assert list_res["evaluations"][0]["location"] == {"id": loc1_id, "name": "BKC Office", "city": "Mumbai"}

        # PATCH to another own location -> updates location
        patch_res = client.patch(
            f"/api/evaluations/{ev_id}",
            headers=auth1,
            json={"location_id": loc1_b_id},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["location"] == {"id": loc1_b_id, "name": "Worli Annex", "city": "Mumbai"}

        # PATCH title without location_id -> preserves location
        patch_title = client.patch(
            f"/api/evaluations/{ev_id}",
            headers=auth1,
            json={"title": "Housekeeping Worli"},
        )
        assert patch_title.status_code == 200
        assert patch_title.json()["location"] == {"id": loc1_b_id, "name": "Worli Annex", "city": "Mumbai"}

        # PATCH with location_id: null -> clears location
        patch_clear = client.patch(
            f"/api/evaluations/{ev_id}",
            headers=auth1,
            json={"location_id": None},
        )
        assert patch_clear.status_code == 200
        assert patch_clear.json()["location"] is None

    # User 2 (different company)
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid2, "u2@vixenone.app")):
        auth2 = {"Authorization": "Bearer token2"}

        # Cross-company 404 on location endpoints
        assert client.patch(f"/api/company/locations/{loc1_id}", headers=auth2, json={"name": "Hacked"}).status_code == 404
        assert client.delete(f"/api/company/locations/{loc1_id}", headers=auth2).status_code == 404

        # Create evaluation with User 1's location_id -> 422 "Unknown location."
        bad_create = client.post(
            "/api/evaluations",
            headers=auth2,
            json={"title": "Cross Company Eval", "category": "Facilities", "location_id": loc1_id},
        )
        assert bad_create.status_code == 422
        assert bad_create.json()["detail"] == "Unknown location."

        # Create evaluation without location, then PATCH with User 1's location_id -> 422 "Unknown location."
        ev2 = client.post(
            "/api/evaluations",
            headers=auth2,
            json={"title": "User 2 Eval", "category": "Facilities"},
        ).json()
        bad_patch = client.patch(
            f"/api/evaluations/{ev2['id']}",
            headers=auth2,
            json={"location_id": loc1_id},
        )
        assert bad_patch.status_code == 422
        assert bad_patch.json()["detail"] == "Unknown location."


def test_demo_seed_twice_company_locations_links_and_housekeeping_totals():
    async def run_seed_twice_and_get_uid():
        async with async_session() as s:
            user = (await s.execute(select(User).where(User.email == DEMO_EMAIL))).scalars().first()
            if not user:
                comp = Company(id=uuid.uuid4(), name=None)
                s.add(comp)
                await s.flush()
                user = User(
                    id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                    company_id=comp.id,
                    firebase_uid="demo-uid-vixenone",
                    email=DEMO_EMAIL,
                    display_name="Priya Sharma",
                )
                s.add(user)
                await s.commit()
            await seed_demo_data(s)
            await seed_demo_data(s)

            # Verify exactly 1 company for demo user and 4 locations
            users = list((await s.execute(select(User).where(User.email == DEMO_EMAIL))).scalars().all())
            assert len(users) == 1
            demo_user = users[0]
            locs = list(
                (await s.execute(select(Location).where(Location.company_id == demo_user.company_id))).scalars().all()
            )
            assert len(locs) == 4
            return demo_user.firebase_uid

    demo_uid = asyncio.run(run_seed_twice_and_get_uid())
    token = {"uid": demo_uid, "email": DEMO_EMAIL, "name": "Priya Sharma"}

    with patch("firebase_admin.auth.verify_id_token", return_value=token):
        auth = {"Authorization": "Bearer demo"}

        # Check GET /api/company
        comp = client.get("/api/company", headers=auth).json()
        assert comp["name"] == "Northbridge Properties Pvt Ltd"
        assert len(comp["locations"]) == 4
        assert [(loc["name"], loc["city"], loc["position"], loc["evaluation_count"]) for loc in comp["locations"]] == [
            ("Andheri East Office", "Mumbai", 0, 1),
            ("Powai Campus", "Mumbai", 1, 1),
            ("BKC Office", "Mumbai", 2, 1),
            ("Thane Warehouse", "Thane", 3, 1),
        ]

        # Check GET /api/evaluations links by title
        evals = client.get("/api/evaluations", headers=auth).json()["evaluations"]
        by_title = {e["title"]: e for e in evals}
        assert by_title["Housekeeping Services — Andheri East Office, FY 2026–27"]["location"]["name"] == "Andheri East Office"
        assert by_title["Security Services — Powai Campus"]["location"]["name"] == "Powai Campus"
        assert by_title["Pantry & Cafeteria — BKC Office"]["location"]["name"] == "BKC Office"
        assert by_title["Pest Control AMC — Thane Warehouse"]["location"]["name"] == "Thane Warehouse"

        # Check Housekeeping totals 64.05 / 86.00 / 57.95 unchanged
        hk_id = by_title["Housekeeping Services — Andheri East Office, FY 2026–27"]["id"]
        results = client.get(f"/api/evaluations/{hk_id}/results", headers=auth).json()
        vendors = {v["name"]: v for v in results["vendors"]}
        assert vendors["BrightNest Facility Services"]["raw_score"] == 64.05
        assert vendors["Shubh Housekeeping Pvt Ltd"]["raw_score"] == 86.0
        assert vendors["UrbanKleen Services"]["raw_score"] == 57.95
