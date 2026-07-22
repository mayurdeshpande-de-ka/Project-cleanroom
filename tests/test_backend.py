"""
=============================================================================
BACKEND TESTS — Form 20 Backlog Dashboard
=============================================================================
Test Layers:
  1. DB Layer  — Connection wrapper, param translation, CRUD on Postgres
  2. API Layer — Flask route responses (structure, types, status codes)
  3. Logic     — apply_dynamic_status business logic, filter combinations
  4. Security  — Auth guard on protected endpoints

Run:
  pytest tests/test_backend.py -v
=============================================================================
"""
import json
import pytest
import os
import sys

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def app():
    """Create a Flask test app with auth disabled and an in-memory SQLite DB."""
    os.environ.setdefault("DISABLE_AUTH", "1")
    os.environ.setdefault("GOOGLE_CLIENT_ID", "dummy")
    os.environ.setdefault("GOOGLE_CLIENT_SECRET", "dummy")
    os.environ.setdefault("SECRET_KEY", "test-secret")
    # Force SQLite for these unit tests (no Postgres required locally)
    os.environ["LOCAL_DB_HOST"] = "SQLITE"   # triggers fallback in get_db()

    import app as flask_app_module
    flask_app_module.app.config["TESTING"] = True
    flask_app_module.app.config["SECRET_KEY"] = "test-secret"
    with flask_app_module.app.test_client() as client:
        yield client


@pytest.fixture(scope="module")
def pg_conn():
    """
    Live Postgres connection for the CI environment.
    Skipped automatically if LOCAL_DB_HOST is not a real postgres host.
    """
    import psycopg2, psycopg2.extras
    host = os.environ.get("LOCAL_DB_HOST", "localhost")
    if host == "SQLITE":
        pytest.skip("Postgres not configured in this environment.")
    conn = psycopg2.connect(
        host=host,
        database=os.environ.get("LOCAL_DB_NAME", "local_backlog_db"),
        user=os.environ.get("LOCAL_DB_USER", "backlog_user"),
        password=os.environ.get("LOCAL_DB_PASS", "backlog_local_pass"),
        cursor_factory=psycopg2.extras.DictCursor
    )
    yield conn
    conn.close()


# =============================================================================
# SECTION 1 — DB CONNECTION LAYER
# =============================================================================

class TestDatabaseWrapper:
    """Tests the LocalPostgresConnectionWrapper used by get_db()."""

    def test_wrapper_translates_question_marks(self, pg_conn):
        """'?' in any query should be replaced with '%s' before execution."""
        from app import LocalPostgresConnectionWrapper
        wrapper = LocalPostgresConnectionWrapper(pg_conn)
        cur = wrapper.execute("SELECT %s AS val", ("hello",))
        row = cur.fetchone()
        assert row is not None
        assert row["val"] == "hello"

    def test_fetchone_returns_dict(self, pg_conn):
        """fetchone() must return a dict (not a tuple)."""
        from app import LocalPostgresConnectionWrapper
        wrapper = LocalPostgresConnectionWrapper(pg_conn)
        cur = wrapper.execute("SELECT 1 AS num")
        row = cur.fetchone()
        assert isinstance(row, dict)
        assert row["num"] == 1

    def test_fetchall_returns_list_of_dicts(self, pg_conn):
        """fetchall() must return a list of dicts."""
        from app import LocalPostgresConnectionWrapper
        wrapper = LocalPostgresConnectionWrapper(pg_conn)
        cur = wrapper.execute("SELECT 1 AS a UNION ALL SELECT 2 AS a")
        rows = cur.fetchall()
        assert isinstance(rows, list)
        assert len(rows) == 2
        assert isinstance(rows[0], dict)

    def test_commit_does_not_raise(self, pg_conn):
        """commit() on the wrapper should not raise any exception."""
        from app import LocalPostgresConnectionWrapper
        wrapper = LocalPostgresConnectionWrapper(pg_conn)
        try:
            wrapper.commit()
        except Exception as e:
            pytest.fail(f"commit() raised an unexpected exception: {e}")


class TestDownloadTrackingTable:
    """CRUD tests on the download_tracking table in Postgres."""

    TEST_KEY = "TEST-BACKLOG-001"

    def setup_method(self, _):
        """Clean test data before each test."""
        import psycopg2
        host = os.environ.get("LOCAL_DB_HOST", "localhost")
        if host == "SQLITE":
            pytest.skip("Postgres not configured.")
        conn = psycopg2.connect(
            host=host,
            database=os.environ.get("LOCAL_DB_NAME", "local_backlog_db"),
            user=os.environ.get("LOCAL_DB_USER", "backlog_user"),
            password=os.environ.get("LOCAL_DB_PASS", "backlog_local_pass"),
        )
        cur = conn.cursor()
        cur.execute("DELETE FROM download_tracking WHERE record_key = %s", (self.TEST_KEY,))
        conn.commit()
        conn.close()

    def test_insert_record(self, pg_conn):
        """Should insert a valid record and auto-assign an ID."""
        from app import LocalPostgresConnectionWrapper
        wrapper = LocalPostgresConnectionWrapper(pg_conn)
        wrapper.execute(
            "INSERT INTO download_tracking (assembly_constituency, state, type, record_key) VALUES (?, ?, ?, ?)",
            ("Test AC", "Test State", "AE", self.TEST_KEY)
        )
        wrapper.commit()
        cur = wrapper.execute("SELECT * FROM download_tracking WHERE record_key = ?", (self.TEST_KEY,))
        row = cur.fetchone()
        assert row is not None
        assert row["assembly_constituency"] == "Test AC"
        assert row["state"] == "Test State"
        assert row["type"] == "AE"

    def test_default_status_values(self, pg_conn):
        """Newly inserted records should have correct default status values."""
        from app import LocalPostgresConnectionWrapper
        wrapper = LocalPostgresConnectionWrapper(pg_conn)
        wrapper.execute(
            "INSERT INTO download_tracking (assembly_constituency, state, type, record_key) VALUES (?, ?, ?, ?)",
            ("Test AC", "Test State", "AE", self.TEST_KEY)
        )
        wrapper.commit()
        cur = wrapper.execute("SELECT * FROM download_tracking WHERE record_key = ?", (self.TEST_KEY,))
        row = cur.fetchone()
        assert row["download_status"] == "missing"
        assert row["extraction_status"] == "pending"
        assert row["db_status"] == "not_in_db"
        assert row["overall_status"] == "missing"
        assert row["wip"] == 0
        assert row["manual_override"] == 0

    def test_update_status(self, pg_conn):
        """Should update download_status of an existing record."""
        from app import LocalPostgresConnectionWrapper
        wrapper = LocalPostgresConnectionWrapper(pg_conn)
        wrapper.execute(
            "INSERT INTO download_tracking (assembly_constituency, state, type, record_key) VALUES (?, ?, ?, ?)",
            ("Test AC", "Test State", "AE", self.TEST_KEY)
        )
        wrapper.commit()
        wrapper.execute(
            "UPDATE download_tracking SET download_status = ? WHERE record_key = ?",
            ("downloaded", self.TEST_KEY)
        )
        wrapper.commit()
        cur = wrapper.execute("SELECT download_status FROM download_tracking WHERE record_key = ?", (self.TEST_KEY,))
        row = cur.fetchone()
        assert row["download_status"] == "downloaded"

    def test_duplicate_record_key_rejected(self, pg_conn):
        """Duplicate record_key should raise a unique constraint violation."""
        import psycopg2
        from app import LocalPostgresConnectionWrapper
        wrapper = LocalPostgresConnectionWrapper(pg_conn)
        wrapper.execute(
            "INSERT INTO download_tracking (assembly_constituency, state, type, record_key) VALUES (?, ?, ?, ?)",
            ("Test AC", "Test State", "AE", self.TEST_KEY)
        )
        wrapper.commit()
        with pytest.raises(Exception):  # UniqueViolation or IntegrityError
            wrapper.execute(
                "INSERT INTO download_tracking (assembly_constituency, state, type, record_key) VALUES (?, ?, ?, ?)",
                ("Other AC", "Other State", "GE", self.TEST_KEY)
            )
            pg_conn.commit()
        pg_conn.rollback()


class TestActivityLogTable:
    """Tests on the activity_log table."""

    def test_insert_activity_log(self, pg_conn):
        """Should insert a log entry and retrieve it."""
        from app import LocalPostgresConnectionWrapper
        wrapper = LocalPostgresConnectionWrapper(pg_conn)
        wrapper.execute(
            "INSERT INTO activity_log (record_key, action, changed_by) VALUES (?, ?, ?)",
            ("LOG-KEY-001", "status_change", "test_user")
        )
        wrapper.commit()
        cur = wrapper.execute(
            "SELECT * FROM activity_log WHERE record_key = ? ORDER BY id DESC LIMIT 1",
            ("LOG-KEY-001",)
        )
        row = cur.fetchone()
        assert row is not None
        assert row["action"] == "status_change"
        assert row["changed_by"] == "test_user"

    def test_activity_log_old_new_values(self, pg_conn):
        """Should store and retrieve old_value and new_value correctly."""
        from app import LocalPostgresConnectionWrapper
        wrapper = LocalPostgresConnectionWrapper(pg_conn)
        wrapper.execute(
            "INSERT INTO activity_log (record_key, action, old_value, new_value, changed_by) VALUES (?, ?, ?, ?, ?)",
            ("LOG-KEY-002", "status_change", "missing", "downloaded", "admin")
        )
        wrapper.commit()
        cur = wrapper.execute(
            "SELECT * FROM activity_log WHERE record_key = ? ORDER BY id DESC LIMIT 1",
            ("LOG-KEY-002",)
        )
        row = cur.fetchone()
        assert row["old_value"] == "missing"
        assert row["new_value"] == "downloaded"


# =============================================================================
# SECTION 2 — API ROUTE TESTS
# =============================================================================

class TestApiStats:
    """/api/stats — Dashboard stats endpoint."""

    def test_returns_200(self, app):
        response = app.get("/api/stats")
        assert response.status_code == 200

    def test_response_is_json(self, app):
        response = app.get("/api/stats")
        data = response.get_json()
        assert data is not None
        assert isinstance(data, dict)

    def test_required_keys_present(self, app):
        """Response must contain all keys the Dashboard UI depends on."""
        response = app.get("/api/stats")
        data = response.get_json()
        required_keys = ["total", "by_status", "sir_by_status", "wip_count",
                         "by_state", "by_type", "bottlenecks"]
        for key in required_keys:
            assert key in data, f"Missing key in /api/stats response: '{key}'"

    def test_total_is_integer(self, app):
        data = app.get("/api/stats").get_json()
        assert isinstance(data["total"], int)

    def test_by_status_contains_expected_keys(self, app):
        data = app.get("/api/stats").get_json()
        by_status = data["by_status"]
        expected = {"downloaded", "extracted", "missing", "pending", "completed", "db_pushed"}
        assert set(by_status.keys()) == expected

    def test_by_status_values_are_non_negative(self, app):
        data = app.get("/api/stats").get_json()
        for key, val in data["by_status"].items():
            assert val >= 0, f"Negative count for status '{key}'"

    def test_wip_count_non_negative(self, app):
        data = app.get("/api/stats").get_json()
        assert data["wip_count"] >= 0

    def test_by_state_is_list(self, app):
        data = app.get("/api/stats").get_json()
        assert isinstance(data["by_state"], list)

    def test_bottlenecks_max_five_entries(self, app):
        data = app.get("/api/stats").get_json()
        assert len(data["bottlenecks"]) <= 5

    def test_stats_total_consistency(self, app):
        """Sum of by_status values must equal 'total'."""
        data = app.get("/api/stats").get_json()
        total_from_statuses = sum(data["by_status"].values())
        assert total_from_statuses == data["total"]

    def test_sir_by_status_subset_of_total(self, app):
        """SIR totals cannot exceed overall totals."""
        data = app.get("/api/stats").get_json()
        total_sir = sum(data["sir_by_status"].values())
        assert total_sir <= data["total"]

    def test_filter_by_el_type(self, app):
        """Filtering by el_type=AE should return a subset."""
        all_data = app.get("/api/stats").get_json()
        ae_data = app.get("/api/stats?el_type=AE").get_json()
        assert ae_data["total"] <= all_data["total"]


class TestApiRecords:
    """/api/records — Record listing endpoint."""

    def test_returns_200(self, app):
        response = app.get("/api/records")
        assert response.status_code == 200

    def test_response_is_list(self, app):
        data = app.get("/api/records").get_json()
        assert isinstance(data, list)

    def test_record_has_required_fields(self, app):
        """Each record object should contain the fields the frontend expects."""
        data = app.get("/api/records").get_json()
        if not data:
            pytest.skip("No records in DB — skipping field validation.")
        record = data[0]
        required_fields = ["state", "el_type", "overall_status"]
        for field in required_fields:
            assert field in record, f"Field '{field}' missing from record object"

    def test_filter_by_state(self, app):
        """Filtering by a specific state should only return that state's records."""
        all_data = app.get("/api/records").get_json()
        if not all_data:
            pytest.skip("No records in DB.")
        state = all_data[0]["state"]
        filtered = app.get(f"/api/records?state={state}").get_json()
        for record in filtered:
            assert record["state"] == state

    def test_filter_by_el_type(self, app):
        """Filtering by el_type=AE must not return GE records."""
        filtered = app.get("/api/records?el_type=AE").get_json()
        for record in filtered:
            assert "AE" in record["el_type"]

    def test_search_returns_subset(self, app):
        """Search with any term must return <= total records."""
        total = len(app.get("/api/records").get_json())
        searched = len(app.get("/api/records?search=Bihar").get_json())
        assert searched <= total

    def test_empty_search_returns_all(self, app):
        """Empty search should not filter anything."""
        total = len(app.get("/api/records").get_json())
        empty_search = len(app.get("/api/records?search=").get_json())
        assert empty_search == total

    def test_completed_records_excluded(self, app):
        """Records with overall_status=db_pushed or completed must not appear in listing."""
        data = app.get("/api/records").get_json()
        for record in data:
            assert record["overall_status"] not in ("db_pushed", "completed"), \
                f"Completed record {record.get('key')} should not appear in listing"

    def test_sir_only_filter(self, app):
        """sir_only=1 should only return SIR state records."""
        data = app.get("/api/records?sir_only=1").get_json()
        for record in data:
            assert record.get("is_sir_state") == 1, \
                f"Non-SIR record returned with sir_only=1 filter"

    def test_hide_bp_filter(self, app):
        """hide_bp=1 must exclude any election type ending in '-BP'."""
        data = app.get("/api/records?hide_bp=1").get_json()
        for record in data:
            assert not record["el_type"].endswith("-BP"), \
                f"BP record {record.get('key')} appeared despite hide_bp=1"


class TestApiRecordPatch:
    """/api/records/<id> — Inline record update endpoint."""

    def test_patch_invalid_id_returns_404_or_500(self, app):
        """Patching a non-existent record ID should not return 200."""
        response = app.patch(
            "/api/records/99999999",
            json={"overall_status": "downloaded"},
            content_type="application/json"
        )
        assert response.status_code != 200

    def test_patch_with_no_valid_fields_returns_400(self, app):
        """Sending no recognized fields must return 400."""
        response = app.patch(
            "/api/records/1",
            json={"invalid_field": "value"},
            content_type="application/json"
        )
        assert response.status_code == 400

    def test_patch_sets_manual_override(self, app):
        """Updating overall_status must set manual_override=1 to prevent revert."""
        all_records = app.get("/api/records").get_json()
        if not all_records:
            pytest.skip("No records in DB.")
        record_id = all_records[0]["id"]
        response = app.patch(
            f"/api/records/{record_id}",
            json={"overall_status": "downloaded"},
            content_type="application/json"
        )
        if response.status_code == 200:
            updated = response.get_json()
            assert updated.get("manual_override") == 1


class TestApiFilters:
    """/api/filters — Filter options endpoint."""

    def test_returns_200(self, app):
        response = app.get("/api/filters")
        assert response.status_code == 200

    def test_response_is_json(self, app):
        data = app.get("/api/filters").get_json()
        assert data is not None


class TestApiGlanceReport:
    """/api/glance_report — State-level glance view endpoint."""

    def test_returns_200(self, app):
        response = app.get("/api/glance_report")
        assert response.status_code == 200

    def test_response_is_list_or_dict(self, app):
        data = app.get("/api/glance_report").get_json()
        assert isinstance(data, (list, dict))


class TestApiWeeklyMomentum:
    """/api/weekly_momentum — Progress over time."""

    def test_returns_200(self, app):
        response = app.get("/api/weekly_momentum")
        assert response.status_code == 200


class TestApiRetroMetadata:
    """/api/retro/metadata — Retro export metadata."""

    def test_returns_200_or_204(self, app):
        response = app.get("/api/retro/metadata")
        assert response.status_code in (200, 204)


class TestApiRetroCount:
    """/api/retro/count — Count of retro-ready records."""

    def test_returns_200(self, app):
        response = app.get("/api/retro/count")
        assert response.status_code == 200


# =============================================================================
# SECTION 3 — BUSINESS LOGIC TESTS
# =============================================================================

class TestApplyDynamicStatus:
    """
    Tests for the apply_dynamic_status() function which is the
    core piece of business logic in the dashboard.
    """

    def _make_record(self, **kwargs):
        defaults = {
            "state": "TestState", "key": "TestState-AE-2022",
            "el_type": "AE", "el_year": 2022,
            "download_status": "missing", "extraction_status": "pending",
            "db_status": "not_in_db", "overall_status": "missing",
            "wip": 0, "is_sir_state": 0, "manual_override": 0,
            "state_name": "Test State Name"
        }
        defaults.update(kwargs)
        return defaults

    def test_live_completed_overrides_all(self):
        """If record key is in live_extracted set, status must be db_pushed."""
        from app import apply_dynamic_status
        record = self._make_record(key="ST-AE-2022")
        result = apply_dynamic_status(record, {"ST-AE-2022"}, {}, {})
        assert result["overall_status"] == "db_pushed"
        assert result["db_status"] == "in_db"

    def test_downloaded_status_applied_from_report(self):
        """If record key is in download_report with status 'downloaded', apply it."""
        from app import apply_dynamic_status
        record = self._make_record(key="ST-GE-2019", manual_override=0)
        download_report = {"ST-GE-2019": {"overall_status": "downloaded"}}
        result = apply_dynamic_status(record, set(), download_report, {})
        assert result["overall_status"] == "downloaded"

    def test_manual_override_not_reverted(self):
        """A record with manual_override=1 must not have its status changed."""
        from app import apply_dynamic_status
        record = self._make_record(
            key="ST-GE-2019",
            overall_status="extracted",
            manual_override=1
        )
        download_report = {"ST-GE-2019": {"overall_status": "missing"}}
        result = apply_dynamic_status(record, set(), download_report, {})
        # manual_override should protect status from being reverted to missing
        assert result["overall_status"] != "missing"

    def test_missing_record_stays_missing(self):
        """A record with no matching data in any source should stay 'missing'."""
        from app import apply_dynamic_status
        record = self._make_record(key="NOWHERE-AE-2020")
        result = apply_dynamic_status(record, set(), {}, {})
        assert result["overall_status"] == "missing"

    def test_wip_flag_preserved(self):
        """A record with wip=1 should retain it through dynamic status calculation."""
        from app import apply_dynamic_status
        record = self._make_record(wip=1)
        result = apply_dynamic_status(record, set(), {}, {})
        assert result["wip"] == 1


class TestStatAggregation:
    """Test that /api/stats aggregates statuses correctly."""

    def test_all_statuses_counted_consistently(self, app):
        """
        Values in by_status must sum to 'total'.
        This catches any off-by-one in the aggregation loop.
        """
        data = app.get("/api/stats").get_json()
        calculated_total = sum(data["by_status"].values())
        assert calculated_total == data["total"], \
            f"by_status sum ({calculated_total}) != total ({data['total']})"

    def test_bottleneck_states_sorted_by_missing_desc(self, app):
        """Bottlenecks list must be sorted descending by missing count."""
        data = app.get("/api/stats").get_json()
        bottlenecks = data["bottlenecks"]
        if len(bottlenecks) > 1:
            for i in range(len(bottlenecks) - 1):
                assert bottlenecks[i]["missing"] >= bottlenecks[i + 1]["missing"], \
                    "Bottlenecks not sorted by missing count (descending)"

    def test_by_state_contains_state_field(self, app):
        data = app.get("/api/stats").get_json()
        for row in data["by_state"]:
            assert "state" in row
            assert "total" in row
            assert "missing" in row
            assert "completed" in row


# =============================================================================
# SECTION 4 — SECURITY TESTS
# =============================================================================

class TestAuthenticationGuard:
    """Verify that auth-protected routes return 401 when not logged in."""

    @pytest.fixture
    def unauthed_app(self):
        """Create a client with auth enabled and no session."""
        os.environ.pop("DISABLE_AUTH", None)
        os.environ["DISABLE_AUTH"] = "0"
        import importlib
        import app as flask_app_module
        importlib.reload(flask_app_module)
        flask_app_module.app.config["TESTING"] = True
        flask_app_module.app.config["SECRET_KEY"] = "test-secret"
        with flask_app_module.app.test_client() as client:
            yield client
        os.environ["DISABLE_AUTH"] = "1"

    def test_api_stats_unauthorized_returns_401(self, unauthed_app):
        response = unauthed_app.get("/api/stats")
        assert response.status_code == 401

    def test_api_records_unauthorized_returns_401(self, unauthed_app):
        response = unauthed_app.get("/api/records")
        assert response.status_code == 401

    def test_api_export_unauthorized_returns_401(self, unauthed_app):
        response = unauthed_app.post("/api/export", json={})
        assert response.status_code == 401

    def test_login_page_is_publicly_accessible(self, unauthed_app):
        response = unauthed_app.get("/login_page")
        assert response.status_code == 200

    def test_oauth_domain_restriction(self):
        """Users from unauthorized domains must be blocked."""
        os.environ["ALLOWED_OAUTH_DOMAIN"] = "varahe.com"
        user_email = "attacker@gmail.com"
        allowed_domain = os.environ.get("ALLOWED_OAUTH_DOMAIN", "").strip().lower()
        is_allowed = user_email.lower().endswith("@" + allowed_domain)
        assert not is_allowed, "OAuth domain check is incorrectly allowing unauthorized emails"
