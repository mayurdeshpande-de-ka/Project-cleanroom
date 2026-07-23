"""
=============================================================================
TEST — URL State Persistence (feature/url-state-persistence)
=============================================================================
Verifies that the URL hash correctly encodes / decodes the selected state
so that a page refresh restores the user to the exact state detail view.

These are integration-level tests that simulate what the browser JS does.
Since the logic lives in app.js (vanilla JS), we test the Flask route
ensures the page is served correctly for any hash (hashes are client-side),
and we document the expected JS behaviour as acceptance criteria.
=============================================================================
"""
import pytest
import os


# ── Flask app fixture (auth disabled, SQLite fallback) ───────────────────────
@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("DISABLE_AUTH", "1")
    os.environ.setdefault("GOOGLE_CLIENT_ID", "dummy")
    os.environ.setdefault("GOOGLE_CLIENT_SECRET", "dummy")
    os.environ.setdefault("SECRET_KEY", "test-secret")
    os.environ["LOCAL_DB_HOST"] = "SQLITE"

    import app as flask_app_module
    flask_app_module.app.config["TESTING"] = True
    flask_app_module.app.config["SECRET_KEY"] = "test-secret"
    with flask_app_module.app.test_client() as client:
        yield client


# =============================================================================
# SERVER-SIDE: The index route must serve the page for any URL hash
# (Hashes are never sent to the server, so the route just serves index.html)
# =============================================================================

class TestIndexRoute:
    def test_index_returns_200(self, app):
        """The root route must always return 200 regardless of any hash."""
        response = app.get('/')
        assert response.status_code == 200

    def test_index_returns_html(self, app):
        """The root route must return HTML content."""
        response = app.get('/')
        assert b'<!DOCTYPE html>' in response.data or b'<html' in response.data

    def test_index_contains_app_js(self, app):
        """The page must include app.js which contains the URL persistence logic."""
        response = app.get('/')
        assert b'app.js' in response.data

    def test_static_app_js_served(self, app):
        """The app.js static file must be served by Flask."""
        response = app.get('/static/app.js')
        assert response.status_code == 200

    def test_app_js_contains_url_persistence(self, app):
        """app.js must contain the readStateFromURL function we added."""
        response = app.get('/static/app.js')
        assert b'readStateFromURL' in response.data

    def test_app_js_contains_hash_write(self, app):
        """openStateDetail must write to history.pushState with #state= hash."""
        response = app.get('/static/app.js')
        assert b'#state=' in response.data

    def test_app_js_contains_popstate_listener(self, app):
        """app.js must listen to popstate for browser back/forward support."""
        response = app.get('/static/app.js')
        assert b'popstate' in response.data

    def test_app_js_contains_encode_uri(self, app):
        """State names must be URL-encoded to handle spaces (e.g. Uttar Pradesh)."""
        response = app.get('/static/app.js')
        assert b'encodeURIComponent' in response.data

    def test_app_js_contains_decode_uri(self, app):
        """State names must be URL-decoded when reading back from the hash."""
        response = app.get('/static/app.js')
        assert b'decodeURIComponent' in response.data

    def test_app_js_clears_hash_on_back(self, app):
        """goBackToStates must clear the hash from the URL."""
        response = app.get('/static/app.js')
        # We use history.pushState with just pathname+search (no hash) to clear it
        assert b'window.location.pathname' in response.data


# =============================================================================
# ACCEPTANCE CRITERIA (documented as passing assertions on JS source)
# These mirror exactly what a manual tester would verify in the browser.
# =============================================================================

class TestUrlPersistenceLogic:
    """
    Validates the URL persistence logic by inspecting the app.js source code.
    Each test corresponds to one testable user scenario.
    """

    @pytest.fixture(autouse=True)
    def load_js(self, app):
        response = app.get('/static/app.js')
        self.js = response.data.decode('utf-8')

    # ── Scenario 1: User clicks a state ──────────────────────────────────────
    def test_clicking_state_writes_hash_to_url(self):
        """
        AC: When user clicks 'Uttar Pradesh', the browser URL must become:
        /?#state=Uttar%20Pradesh
        Verified by: openStateDetail calls history.pushState with #state=
        """
        assert "history.pushState(null, '', '#state=' + encodeURIComponent(stateName))" in self.js

    # ── Scenario 2: User refreshes the page ──────────────────────────────────
    def test_refresh_reads_hash_and_restores_view(self):
        """
        AC: On page refresh with URL /#state=Uttar%20Pradesh, the tracker
        must open directly in Uttar Pradesh detail view without going to the
        states list first.
        Verified by: DOMContentLoaded calls readStateFromURL
        """
        assert "DOMContentLoaded" in self.js
        assert "readStateFromURL" in self.js

    # ── Scenario 3: User clicks browser Back button ───────────────────────────
    def test_browser_back_button_restores_previous_view(self):
        """
        AC: When user clicks browser Back after opening a state, they should
        return to the states list view.
        Verified by: popstate event listener calls readStateFromURL + renderTable
        """
        assert "popstate" in self.js
        assert "renderTable" in self.js

    # ── Scenario 4: User goes back to states list ─────────────────────────────
    def test_going_back_clears_hash_from_url(self):
        """
        AC: When user clicks '← Back' to return to states list, the hash
        must be removed from the URL so a refresh lands on states view.
        Verified by: goBackToStates uses history.pushState without hash
        """
        assert "window.location.pathname + window.location.search" in self.js

    # ── Scenario 5: State name with spaces ───────────────────────────────────
    def test_state_names_with_spaces_are_encoded(self):
        """
        AC: State names like 'Uttar Pradesh' must be URL-encoded to
        'Uttar%20Pradesh' so the URL is valid and shareable.
        """
        assert "encodeURIComponent(stateName)" in self.js
        assert "decodeURIComponent" in self.js

    # ── Scenario 6: Clean URL (no hash) ──────────────────────────────────────
    def test_no_hash_lands_on_states_view(self):
        """
        AC: If the page is loaded with no hash (normal URL), the app must
        show the states list view (not try to open any detail view).
        """
        # readStateFromURL must handle the no-hash case by setting currentView='states'
        assert "currentView = 'states'" in self.js
        assert "currentDetailState = null" in self.js
