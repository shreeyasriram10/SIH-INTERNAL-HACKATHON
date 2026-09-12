import io
import os
import sys
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app  # noqa: E402
import auth  # noqa: E402
from services import copilot, decision_engine, model_registry, rate_horizon  # noqa: E402

DEMO_EMAIL = "admin@sail.gov.in"
DEMO_PASSWORD = "12345"


@pytest.fixture(scope="session")
def _app_client():
    # The context manager runs the lifespan hook, which creates the schema and
    # seeds reference data - the API tests depend on both.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client(_app_client):
    """An anonymous caller.

    Cookies are cleared before each test so a sign-in elsewhere cannot leak a
    session into the checks that must be rejected.
    """
    _app_client.cookies.clear()
    return _app_client


@pytest.fixture(scope="session", autouse=True)
def ensure_model():
    """Make sure a usable model exists before any test asks for a prediction."""
    model_registry.get_payload()


@pytest.fixture(scope="session")
def auth_headers():
    """Bearer credentials for the programmatic-client path.

    Obtained through a throwaway client: logging in via the shared `client`
    would leave a session cookie on it, and the tests that assert endpoints
    reject anonymous callers would then be signed in.
    """
    with TestClient(app) as throwaway:
        response = throwaway.post(
            "/api/auth/login",
            json={"username": DEMO_EMAIL, "password": DEMO_PASSWORD},
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def db_user_factory(_app_client):
    """Create a user directly and hand back a client signed in as them."""
    from database import SessionLocal
    import models as _m

    created = []

    def _make(email, role, password="Str0ngPass!23"):
        with SessionLocal() as session:
            user = session.query(_m.User).filter(_m.User.email == email).first()
            if user is None:
                user = _m.User(name=email.split("@")[0], email=email,
                               hashed_password=auth.get_password_hash(password),
                               role=role)
                session.add(user)
                session.commit()
                session.refresh(user)
            user_id = user.id
        signed_in = TestClient(app)
        response = signed_in.post("/api/auth/login",
                                  json={"username": email, "password": password})
        assert response.status_code == 200, response.text
        created.append(signed_in)
        return {"id": user_id, "client": signed_in, "email": email}

    yield _make
    for c in created:
        c.close()


@pytest.fixture(scope="session")
def auth_client():
    """A client holding a signed-in session.

    Login sets an httpOnly cookie and TestClient keeps it for the life of the
    instance, so this behaves like a signed-in browser. Kept separate from
    `client`, which must stay anonymous to prove the endpoints reject it.
    """
    with TestClient(app) as signed_in:
        response = signed_in.post(
            "/api/auth/login",
            json={"username": DEMO_EMAIL, "password": DEMO_PASSWORD},
        )
        assert response.status_code == 200, response.text
        assert auth.SESSION_COOKIE in signed_in.cookies, "login set no session cookie"
        yield signed_in


# ---------- 1. PAGE ROUTING ----------
class TestPageRoutes:
    def test_root_serves_signin_gateway(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "LOHA DRISHTI" in r.text
        assert "Ministry of Steel" in r.text
        assert "Secure Authentication" in r.text

    def test_app_serves_dashboard(self, client):
        r = client.get("/app")
        assert r.status_code == 200
        assert "LOHA DRISHTI" in r.text
        assert "Command Centre" in r.text

    def test_ml_training_page_serves(self, client):
        r = client.get("/ml-training")
        assert r.status_code == 200
        assert "ML Model" in r.text

    def test_system_verification_page_serves(self, client):
        r = client.get("/verification")
        assert r.status_code == 200
        assert "System Verification" in r.text

    def test_healthz(self, client):
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_api_docs_accessible(self, client):
        assert client.get("/docs").status_code == 200

    @pytest.mark.parametrize("path", ["/", "/app", "/ml-training", "/verification"])
    def test_pages_are_not_cacheable(self, client, path):
        """A redeploy must reach browsers that already loaded the page.

        FileResponse sends Last-Modified from the file mtime, and Vercel freezes
        deployed mtimes, so the value never changed between builds: browsers
        revalidated, got a 304, and kept serving the previous build's HTML.
        The shells must therefore carry no validator at all.
        """
        response = client.get(path)
        assert response.status_code == 200
        assert "no-store" in response.headers.get("cache-control", "")
        assert "last-modified" not in response.headers
        assert "etag" not in response.headers

    def test_conditional_request_still_returns_fresh_html(self, client):
        response = client.get(
            "/app", headers={"If-Modified-Since": "Sat, 20 Oct 2018 01:46:40 GMT"}
        )
        assert response.status_code == 200, "a 304 here means stale HTML in the browser"
        assert "LOHA DRISHTI" in response.text


# ---------- 2. AUTHENTICATION ----------
class TestAuthAPI:
    def test_login_form_encoded(self, client):
        r = client.post(
            "/api/auth/login",
            data={"username": DEMO_EMAIL, "password": DEMO_PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["token_type"] == "bearer"
        assert body["role"] == "Admin"

    def test_login_json_body(self, client):
        r = client.post(
            "/api/auth/login", json={"username": DEMO_EMAIL, "password": DEMO_PASSWORD}
        )
        assert r.status_code == 200
        assert r.json()["access_token"]

    def test_login_invalid_password(self, client):
        r = client.post(
            "/api/auth/login",
            json={"username": DEMO_EMAIL, "password": "wrongpassword999"},
        )
        assert r.status_code == 401

    def test_login_unknown_user(self, client):
        r = client.post(
            "/api/auth/login",
            json={"username": "nobody@example.com", "password": DEMO_PASSWORD},
        )
        assert r.status_code == 401

    def test_demo_password_is_not_a_bypass(self, client):
        """The demo password must only work for accounts that really hold it -
        it used to authenticate any address in a hardcoded list."""
        r = client.post(
            "/api/auth/login",
            json={"username": "attacker@sail.gov.in", "password": DEMO_PASSWORD},
        )
        assert r.status_code == 401

    def test_me_requires_token(self, client):
        assert client.get("/api/auth/me").status_code == 401

    def test_me_rejects_garbage_token(self, client):
        r = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
        assert r.status_code == 401

    def test_me_with_valid_token(self, client, auth_headers):
        r = client.get("/api/auth/me", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["email"] == DEMO_EMAIL


# ---------- 3. PROTECTED ENDPOINTS ----------
class TestAuthorization:
    @pytest.mark.parametrize(
        "method,path,payload",
        [
            ("get", "/api/cargo/", None),
            ("get", "/api/decision/history", None),
            ("get", "/api/system/reports", None),
            ("post", "/api/ml/train", {}),
        ],
    )
    def test_requires_authentication(self, client, method, path, payload):
        call = getattr(client, method)
        response = call(path) if payload is None else call(path, json=payload)
        assert response.status_code in (401, 403), f"{path} -> {response.status_code}"

    def test_report_save_requires_auth(self, client):
        r = client.post("/api/system/reports/save", json={"title": "x"})
        assert r.status_code in (401, 403)

    def test_report_save_with_auth(self, client, auth_headers):
        r = client.post(
            "/api/system/reports/save",
            json={"title": "Test Strategy Report", "cost_cr": 12.5},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "SUCCESS"


# ---------- 4. REFERENCE DATA ----------
class TestReferenceData:
    def test_ports_seeded(self, auth_client):
        r = auth_client.get("/api/ports/")
        assert r.status_code == 200
        ports = r.json()
        assert len(ports) >= 5
        assert {"Paradip", "Dhamra", "Haldia"} <= {p["name"] for p in ports}
        for port in ports:
            assert port["draft_m"] > 0
            assert port["mech_rate_mt_d"] > 0

    def test_vessels_seeded(self, auth_client):
        r = auth_client.get("/api/vessels/")
        assert r.status_code == 200
        classes = {v["class_type"] for v in r.json()}
        assert {"Handysize", "Supramax", "Panamax", "Capesize"} <= classes


# ---------- 5. ML PIPELINE ----------
class TestMLPipeline:
    def test_ml_info(self, auth_client):
        r = auth_client.get("/api/ml/info")
        assert r.status_code == 200
        data = r.json()
        assert data["r2_score"] > 0.90
        assert data["mae_usd"] > 0

    def test_ml_prediction(self, auth_client):
        r = auth_client.post(
            "/api/ml/predict",
            json={
                "origin": "Australia",
                "distance_nm": 4500,
                "month": 6,
                "bunker_price": 640.0,
                "pressure_index": 45.0,
            },
        )
        assert r.status_code == 200
        data = r.json()
        lower, upper = data["confidence_interval"]
        assert 10.0 < data["predicted_rate_usd"] < 70.0
        assert lower <= data["predicted_rate_usd"] <= upper

    def test_ml_prediction_rejects_bad_input(self, auth_client):
        r = auth_client.post(
            "/api/ml/predict",
            json={
                "origin": "Australia",
                "distance_nm": -10,
                "month": 99,
                "bunker_price": 640.0,
                "pressure_index": 45.0,
            },
        )
        assert r.status_code == 422

    def test_forecast_curve(self, auth_client):
        r = auth_client.post(
            "/api/ml/forecast-curve",
            json={
                "origin": "Australia",
                "distance_nm": 4500,
                "month": 3,
                "bunker_price": 700.0,
                "pressure_index": 50.0,
                "horizons": [7, 30, 90],
            },
        )
        assert r.status_code == 200
        points = r.json()["points"]
        assert [p["horizon_days"] for p in points] == [7, 30, 90]
        assert all(p["predicted_rate_usd"] > 0 for p in points)

    def test_model_is_cached_between_calls(self):
        """get_payload must hand back the same object, not reload the pickle."""
        assert model_registry.get_payload() is model_registry.get_payload()

    def test_higher_bunker_price_raises_the_rate(self):
        cheap, dear = model_registry.predict_rates([
            {"origin": "Australia", "distance_nm": 4500, "month": 5,
             "bunker_price": 550.0, "pressure_index": 50.0},
            {"origin": "Australia", "distance_nm": 4500, "month": 5,
             "bunker_price": 850.0, "pressure_index": 50.0},
        ])
        assert dear > cheap


# ---------- 6. DECISION ENGINE ----------
class TestDecisionEngine:
    BASE_REQUEST = {
        "parcel_size": 80000,
        "cargo_type": "Coking Coal",
        "origin": "Australia",
        "plant": "Rourkela",
        "window_days": 30,
        "persist": False,
    }

    def test_optimize_returns_ranked_options(self, auth_client):
        r = auth_client.post("/api/decision/optimize", json=self.BASE_REQUEST)
        assert r.status_code == 200
        body = r.json()
        options = body["options"]
        assert options, "no options returned"
        assert body["recommended"]["landed_cost_usd_mt"] == options[0]["landed_cost_usd_mt"]

        adjusted = [
            o["landed_cost_usd_mt"] * (1 + decision_engine.RISK_WEIGHT * o["risk_index"] / 100)
            for o in options
        ]
        assert adjusted == sorted(adjusted), "options are not ranked by risk-adjusted cost"

    def test_cost_components_sum_to_the_total(self, auth_client):
        r = auth_client.post("/api/decision/optimize", json=self.BASE_REQUEST)
        for option in r.json()["options"]:
            parts = (
                option["ocean_freight_usd"] + option["deadfreight_usd"]
                + option["vessel_hire_usd"] + option["port_dues_usd"]
                + option["demurrage_usd"] + option["lightering_usd"]
                + option["inland_rail_usd"]
            )
            assert parts == pytest.approx(option["landed_cost_usd"], rel=1e-6)

    def test_supply_continuity_does_not_saturate(self, auth_client):
        """The score used to be `50 + slack x 100` clamped to 100, so any cycle
        shorter than half the window read a flat 100/100 - a delivery guarantee
        no charter can offer. It must stay below the ceiling and vary."""
        scores = []
        for origin in ("Australia", "Indonesia", "South Africa", "USA"):
            for window in (20, 30, 45):
                r = auth_client.post("/api/decision/optimize", json={
                    **self.BASE_REQUEST, "origin": origin, "window_days": window,
                })
                if r.status_code != 200:
                    continue
                best = r.json()["recommended"]
                scores.append(best["supply_continuity"])
                assert 0 < best["supply_continuity"] < 100, best["supply_continuity"]

        assert len(scores) >= 8
        assert len(set(scores)) > len(scores) // 2, "score barely discriminates"

    def test_supply_continuity_falls_as_risk_rises(self, auth_client):
        """A calm month and a cyclone month must not score the same."""
        calm = auth_client.post("/api/decision/optimize",
                           json={**self.BASE_REQUEST, "month": 2}).json()["recommended"]
        rough = auth_client.post("/api/decision/optimize",
                            json={**self.BASE_REQUEST, "month": 7}).json()["recommended"]
        assert rough["risk_index"] > calm["risk_index"]
        assert rough["supply_continuity"] < calm["supply_continuity"]

    def test_supply_continuity_falls_as_the_window_tightens(self, auth_client):
        roomy = auth_client.post("/api/decision/optimize",
                            json={**self.BASE_REQUEST, "window_days": 60}).json()["recommended"]
        tight = auth_client.post("/api/decision/optimize",
                            json={**self.BASE_REQUEST, "window_days": 18}).json()["recommended"]
        assert tight["supply_continuity"] < roomy["supply_continuity"]

    def test_explanation_is_populated(self, auth_client):
        r = auth_client.post("/api/decision/optimize", json=self.BASE_REQUEST)
        assert len(r.json()["recommended"]["explanation"]) > 40

    def test_small_parcel_picks_a_small_ship(self, auth_client):
        r = auth_client.post(
            "/api/decision/optimize", json={**self.BASE_REQUEST, "parcel_size": 35000}
        )
        best = r.json()["recommended"]
        assert best["vessel_class"] == "Handysize"
        assert best["utilisation_pct"] > 80

    def test_large_parcel_picks_a_large_ship(self, auth_client):
        r = auth_client.post(
            "/api/decision/optimize", json={**self.BASE_REQUEST, "parcel_size": 170000}
        )
        assert r.json()["recommended"]["vessel_class"] == "Capesize"

    def test_monsoon_month_raises_risk(self, auth_client):
        dry = auth_client.post("/api/decision/optimize", json={**self.BASE_REQUEST, "month": 2})
        wet = auth_client.post("/api/decision/optimize", json={**self.BASE_REQUEST, "month": 7})
        assert wet.json()["recommended"]["risk_index"] > dry.json()["recommended"]["risk_index"]

    def test_invalid_parcel_is_rejected(self, auth_client):
        r = auth_client.post("/api/decision/optimize", json={**self.BASE_REQUEST, "parcel_size": 0})
        assert r.status_code == 422

    def test_optimize_persists_a_recommendation(self, auth_client, auth_headers):
        """Compare the newest row rather than a page count - /history returns a
        capped page, so once it is full the count stops moving."""
        def newest_id():
            page = auth_client.get(
                "/api/decision/history?limit=1", headers=auth_headers
            ).json()["items"]
            return page[0]["id"] if page else None

        before = newest_id()
        auth_client.post(
            "/api/decision/optimize",
            json={**self.BASE_REQUEST, "persist": True},
            headers=auth_headers,
        )
        after = newest_id()
        assert after is not None
        assert after != before

    def test_port_blocked_scenario_diverts(self, auth_client):
        r = auth_client.post(
            "/api/decision/simulate",
            json={**self.BASE_REQUEST, "scenario": "port_blocked", "blocked_port": "Dhamra"},
        )
        assert r.status_code == 200
        assert r.json()["disrupted"]["port_name"] != "Dhamra"

    def test_bunker_spike_costs_more(self, auth_client):
        r = auth_client.post(
            "/api/decision/simulate", json={**self.BASE_REQUEST, "scenario": "bunker_spike"}
        )
        assert r.status_code == 200
        assert r.json()["delta_usd"] > 0

    def test_vessel_unavailable_scenario_switches_class(self, auth_client):
        r = auth_client.post(
            "/api/decision/simulate",
            json={
                **self.BASE_REQUEST,
                "parcel_size": 170000,
                "scenario": "vessel_unavail",
                "unavailable_class": "Capesize",
            },
        )
        assert r.status_code == 200
        assert r.json()["disrupted"]["vessel_class"] != "Capesize"


# ---------- 7. SYSTEM ----------
class TestDatabaseAndSystem:
    def test_system_status(self, auth_client):
        r = auth_client.get("/api/system/status")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "OPERATIONAL"
        assert data["database"]["status"] == "Connected"

    def test_live_system_tests(self, auth_client):
        r = auth_client.get("/api/system/run-tests")
        assert r.status_code == 200
        data = r.json()
        assert data["failed"] == 0, data["results"]
        assert data["overall_status"] == "ALL_TESTS_PASSING"

    def test_waterways(self, client):
        r = client.get("/api/waterways")
        assert r.status_code == 200
        body = r.json()
        assert len(body["waterways"]) >= 10
        assert len(body["vessels"]) >= 5


# ---------- 8. ROLLING FORECAST WINDOW ----------
class TestRateHorizonWindow:
    """The chart window must be derived from the current date on every call,
    and the forecast must join the historical leg without a step.

    Both properties used to be broken: the window was drawn from a fixed
    fraction of the chart width with today pinned to the left edge, and the
    two legs were independent series.
    """

    MARKET = {
        "origin": "Australia",
        "distance_nm": 4500.0,
        "bunker_price": 697.0,
        "pressure_index": 52.5,
    }

    def build(self, today, horizon_days=30, history_days=14):
        return rate_horizon.build_horizon(
            today=today, horizon_days=horizon_days, history_days=history_days,
            **self.MARKET
        )

    # --- rolling window --------------------------------------------------
    def test_forecast_day_one_is_tomorrow(self):
        today = date(2026, 3, 17)
        window = self.build(today)
        first = window["forecast"][0]
        assert first["date"] == (today + timedelta(days=1)).isoformat()
        assert first["day_offset"] == 1

    def test_history_ends_today(self):
        today = date(2026, 3, 17)
        window = self.build(today)
        last = window["history"][-1]
        assert last["date"] == today.isoformat()
        assert last["day_offset"] == 0

    def test_window_shifts_forward_with_the_calendar(self):
        """The regression guard: advancing the clock by one day must move every
        point by exactly one day. A hardcoded or stored anchor fails here."""
        today = date(2026, 3, 17)
        first = self.build(today)
        second = self.build(today + timedelta(days=1))

        dates_a = [p["date"] for p in first["history"] + first["forecast"]]
        dates_b = [p["date"] for p in second["history"] + second["forecast"]]
        assert len(dates_a) == len(dates_b) == 44

        for earlier, later in zip(dates_a, dates_b):
            delta = date.fromisoformat(later) - date.fromisoformat(earlier)
            assert delta == timedelta(days=1), f"{earlier} -> {later}"

    def test_window_is_not_pinned_to_any_stored_date(self):
        """Windows a year apart must not overlap at all."""
        early = self.build(date(2026, 1, 10))
        late = self.build(date(2027, 1, 10))
        early_dates = {p["date"] for p in early["history"] + early["forecast"]}
        late_dates = {p["date"] for p in late["history"] + late["forecast"]}
        assert not (early_dates & late_dates)

    def test_span_matches_the_requested_horizon(self):
        today = date(2026, 3, 17)
        for horizon in (7, 30, 90):
            window = self.build(today, horizon_days=horizon)
            forecast = window["forecast"]
            assert len(forecast) == horizon
            assert forecast[-1]["date"] == (today + timedelta(days=horizon)).isoformat()

    def test_window_crosses_a_year_boundary_cleanly(self):
        today = date(2026, 12, 20)
        window = self.build(today, horizon_days=30)
        assert window["forecast"][-1]["date"] == "2027-01-19"
        assert all(p["rate_usd"] > 0 for p in window["forecast"])

    # --- day-1 anchoring --------------------------------------------------
    def test_day_one_equals_the_last_historical_value(self):
        """The other regression guard: no step at the TODAY divider."""
        window = self.build(date(2026, 3, 17))
        assert window["forecast"][0]["rate_usd"] == window["history"][-1]["rate_usd"]

    def test_the_join_is_not_a_visible_jump(self):
        """The step across the divider must be no worse than an ordinary
        day-to-day move, at every horizon."""
        for horizon in (7, 30, 90):
            window = self.build(date(2026, 7, 3), horizon_days=horizon)
            history, forecast = window["history"], window["forecast"]
            join = abs(forecast[0]["rate_usd"] - history[-1]["rate_usd"])

            series = [p["rate_usd"] for p in history + forecast]
            steps = [abs(b - a) for a, b in zip(series, series[1:])]
            assert join <= max(steps) + 1e-9, f"horizon {horizon}: join {join}"
            assert join == 0

    def test_anchor_reports_what_it_did(self):
        window = self.build(date(2026, 3, 17))
        anchor = window["anchor"]
        expected = anchor["last_historical_usd"] - anchor["model_day_one_raw_usd"]
        assert anchor["offset_applied_usd"] == pytest.approx(expected, abs=0.011)

    def test_offset_decays_so_the_tail_is_the_raw_model(self):
        """Anchoring must not permanently displace the curve - the far end
        should be the model's own level again."""
        today = date(2026, 3, 17)
        window = self.build(today, horizon_days=60)
        tail = window["forecast"][-1]
        raw = rate_horizon._seasonal_rates(
            [date.fromisoformat(tail["date"])], **self.MARKET
        )[0]
        assert tail["rate_usd"] == pytest.approx(raw, abs=0.011)

    def test_daily_series_is_smooth_not_month_stepped(self):
        """The model only sees `month`, so an un-interpolated daily series
        would be flat within a month and jump at the boundary."""
        window = self.build(date(2026, 5, 20), horizon_days=60)
        rates = [p["rate_usd"] for p in window["forecast"]]
        assert len(set(rates)) > 10, "series looks like a month-wise step function"

    def test_confidence_band_widens_with_distance(self):
        window = self.build(date(2026, 3, 17), horizon_days=30)
        forecast = window["forecast"]
        near = forecast[0]["ci_upper_usd"] - forecast[0]["ci_lower_usd"]
        far = forecast[-1]["ci_upper_usd"] - forecast[-1]["ci_lower_usd"]
        assert far > near

    # --- through the API --------------------------------------------------
    def test_endpoint_anchors_to_the_server_clock(self, auth_client):
        r = auth_client.post(
            "/api/ml/rate-horizon",
            json={"origin": "Australia", "horizon_days": 30, "history_days": 14},
        )
        assert r.status_code == 200
        body = r.json()

        today = date.today()
        assert body["today"] == today.isoformat()
        assert body["history"][-1]["date"] == today.isoformat()
        assert body["forecast"][0]["date"] == (today + timedelta(days=1)).isoformat()
        assert body["forecast"][0]["rate_usd"] == body["history"][-1]["rate_usd"]

    def test_endpoint_takes_no_date_or_month_input(self):
        """A start date or month field would let a caller pin the window."""
        from routers.ml import RateHorizonRequest

        fields = set(RateHorizonRequest.model_fields)
        assert not (fields & {"month", "start_date", "today", "anchor_date"})

    def test_endpoint_rejects_an_out_of_range_horizon(self, auth_client):
        r = auth_client.post(
            "/api/ml/rate-horizon", json={"origin": "Australia", "horizon_days": 5000}
        )
        assert r.status_code == 422


# ---------- 9. SHELL CACHE ----------
class TestPageCacheFreshness:
    def test_edit_on_disk_is_served_without_a_restart(self, client):
        """The in-memory page cache must be keyed on the file, not the process.

        Holding the body for the process lifetime is fine on a platform where
        every release starts new containers, but locally it made each edit to
        a shell invisible until the server was bounced.
        """
        import main

        path = os.path.join(main.STATIC_DIR, "app.html")
        original = io.open(path, encoding="utf-8").read()
        marker = "<!-- cache-freshness-probe -->"
        try:
            assert marker not in client.get("/app").text

            io.open(path, "w", encoding="utf-8", newline="").write(original + marker)
            assert marker in client.get("/app").text, "edit not picked up without a restart"
        finally:
            io.open(path, "w", encoding="utf-8", newline="").write(original)

        assert marker not in client.get("/app").text


# ---------- 10. SAVING METRIC ----------
class TestOptimisationSavingBasis:
    """The dashboard reports the saving against the median feasible option.

    It used to compare the winner with the runner-up, which is nearly always a
    near-twin - same origin and vessel class, an adjacent berth whose rail and
    waiting costs cancel - so the figure resolved to fractions of a cent and
    displayed as $0/MT. These guard the data assumptions the replacement rests on.
    """

    REQUEST = {
        "parcel_size": 80000,
        "cargo_type": "Coking Coal",
        "origin": "Australia",
        "plant": "Rourkela",
        "window_days": 30,
        "top_n": 25,
        "persist": False,
    }

    def _totals(self, auth_client, **overrides):
        response = auth_client.post(
            "/api/decision/optimize", json={**self.REQUEST, **overrides}
        )
        assert response.status_code == 200
        return sorted(o["landed_cost_usd_mt"] for o in response.json()["options"])

    def test_runner_up_understates_the_saving(self, auth_client):
        """Why the saving is measured against the median, not the runner-up.

        The second-ranked option is usually a near-twin of the winner, so the
        gap to it understates what optimisation bought. This used to assert a
        fixed "within $1" for one parcel, which stopped holding once cargo
        density entered the model; the property that actually matters is that
        the runner-up gap is smaller than the median gap."""
        totals = self._totals(auth_client)
        assert len(totals) >= 3
        runner_up_gap = totals[1] - totals[0]
        median_gap = totals[len(totals) // 2] - totals[0]
        assert runner_up_gap < median_gap, (runner_up_gap, median_gap)

    def test_median_gives_a_material_saving(self, auth_client):
        totals = self._totals(auth_client)
        median = totals[len(totals) // 2]
        saving = median - totals[0]
        assert saving > 0.5, f"saving vs median is only ${saving:.2f}/MT"

    def test_shortlist_spread_is_wide_enough_to_be_worth_optimising(self, auth_client):
        totals = self._totals(auth_client)
        assert totals[-1] - totals[0] > 5.0


# ---------- 11. SUPPLY CONTINUITY RESPONSIVENESS ----------
class TestSupplyContinuityMoves:
    REQUEST = {
        "parcel_size": 80000,
        "cargo_type": "Coking Coal",
        "origin": "Australia",
        "plant": "Rourkela",
        "persist": False,
    }

    def _score(self, auth_client, **overrides):
        response = auth_client.post(
            "/api/decision/optimize", json={**self.REQUEST, **overrides}
        )
        assert response.status_code == 200
        return response.json()["recommended"]

    def test_a_tighter_window_lowers_continuity(self, auth_client):
        tight = self._score(auth_client, window_days=15)["supply_continuity"]
        roomy = self._score(auth_client, window_days=60)["supply_continuity"]
        assert tight < roomy, f"{tight} not below {roomy}"

    def test_continuity_spans_a_useful_range(self, auth_client):
        """A score that barely moves reads as broken even when it is computed."""
        scores = {
            self._score(auth_client, window_days=days)["supply_continuity"]
            for days in (12, 15, 20, 30, 45, 60, 90)
        }
        assert len(scores) >= 5, f"only {len(scores)} distinct values: {scores}"
        assert max(scores) - min(scores) > 25

    def test_factors_are_returned_so_the_score_can_be_explained(self, auth_client):
        """The card names the binding factor; it needs all three to do that."""
        best = self._score(auth_client, window_days=30)
        for field in (
            "schedule_headroom_pct",
            "continuity_risk_factor_pct",
            "execution_factor_pct",
        ):
            assert field in best, f"missing {field}"
            assert 0 <= best[field] <= 100

    def test_continuity_never_claims_certainty(self, auth_client):
        for days in (30, 60, 120, 365):
            assert self._score(auth_client, window_days=days)["supply_continuity"] <= 97


# ---------- 12. SHARED SHELL ----------
class TestSharedShell:
    """The three served pages must stay on one stylesheet and one chrome.

    ml_training and verification each carried their own near-identical copy of
    the design tokens and the pre-redesign navigation, so they drifted away from
    the dashboard's look and offered no obvious way back to it.
    """

    PAGES = ["/app", "/ml-training", "/verification"]

    @pytest.mark.parametrize("path", PAGES)
    def test_page_uses_the_shared_stylesheet(self, client, path):
        assert "/static/gov-shell.css" in client.get(path).text

    @pytest.mark.parametrize("path", PAGES)
    def test_page_wears_the_government_chrome(self, client, path):
        body = client.get(path).text
        for marker in ("gov-strip", "masthead", "tricolour", "crumbbar", "gov-footer"):
            assert marker in body, f"{path} is missing {marker}"

    @pytest.mark.parametrize("path", ["/ml-training", "/verification"])
    def test_secondary_pages_offer_a_way_back(self, client, path):
        """A reader who lands here must be able to leave without the browser's
        back button."""
        body = client.get(path).text
        assert "btn-back" in body
        assert "Back to Dashboard" in body
        assert 'href="/app"' in body

    def test_shell_stylesheet_is_served(self, client):
        response = client.get("/static/gov-shell.css")
        assert response.status_code == 200
        assert ":root" in response.text

    def test_only_the_shared_sheet_defines_the_tokens(self, client):
        """A page redeclaring :root is how the copies diverged last time."""
        for path in ["/ml-training", "/verification"]:
            assert ":root" not in client.get(path).text, f"{path} redeclares tokens"

    def test_map_cannot_paint_over_the_sticky_chrome(self, client):
        """Leaflet gives its panes z-index 400 and controls up to 1000, which
        beat the header (120) and cargo bar (90) unless the map container owns a
        stacking context. Without one the map slid over both while scrolling.
        """
        body = client.get("/app").text
        start = body.index(".waterways-map-shell{")
        rule = body[start:body.index("}", start)]
        assert "isolation:isolate" in rule, rule
        assert "z-index:0" in rule, rule

    # Typographic marks that carry meaning and are deliberately kept.
    ALLOWED = set("\u2713\u2717\u2715\u2192\u2190\u2605\u21ba")

    @pytest.mark.parametrize("path", PAGES)
    def test_pages_carry_no_emoji(self, client, path):
        body = client.get(path).text
        found = {
            ch for ch in body
            if ch not in self.ALLOWED and (
                0x1F000 <= ord(ch) <= 0x1FAFF
                or 0x2600 <= ord(ch) <= 0x27BF
                or 0x2B00 <= ord(ch) <= 0x2BFF
                or ord(ch) == 0xFE0F
            )
        }
        assert not found, f"{path} still has emoji: {[hex(ord(c)) for c in found]}"


# ---------- 13. CONFIDENTIALITY CONTROLS ----------
class TestConfidentialityControls:
    """Guards for the Tier 0 hardening.

    An audit found that a stranger could self-register, was handed an Analyst
    role, and could then read the organisation's cargo pipeline and priced
    recommendations - while the decision engine, port tariffs and charter rates
    needed no session at all.
    """

    # --- registration is no longer a way in --------------------------------
    def test_self_registration_is_closed_by_default(self, client):
        r = client.post("/api/auth/register", json={
            "name": "Outside Party",
            "email": "stranger@example.com",
            "password": "whatever123",
        })
        assert r.status_code == 403, r.text
        assert "administrator" in r.json()["detail"].lower()

    def test_registration_honours_the_domain_allow_list(self, client, monkeypatch):
        monkeypatch.setattr(auth, "SIGNUP_DOMAINS", ["sail.in"])
        assert auth.signup_allowed("officer@sail.in")
        assert auth.signup_allowed("officer@plant.sail.in")   # subdomain
        assert not auth.signup_allowed("attacker@sail.in.evil.com")
        assert not auth.signup_allowed("someone@example.com")

    # --- the commercially sensitive endpoints need a session ---------------
    @pytest.mark.parametrize("method,path,payload", [
        ("post", "/api/decision/optimize", {
            "parcel_size": 80000, "cargo_type": "Coking Coal", "origin": "Australia",
            "plant": "Rourkela", "window_days": 30}),
        ("post", "/api/decision/simulate", {
            "parcel_size": 80000, "cargo_type": "Coking Coal", "origin": "Australia",
            "plant": "Rourkela", "window_days": 30, "scenario": "cyclone"}),
        ("get", "/api/ports/", None),
        ("get", "/api/vessels/", None),
        ("get", "/api/system/status", None),
        ("get", "/api/system/run-tests", None),
        ("post", "/api/ml/predict", {
            "origin": "Australia", "distance_nm": 4500, "month": 6,
            "bunker_price": 640.0, "pressure_index": 45.0}),
        ("get", "/api/ml/info", None),
        ("post", "/api/ml/rate-horizon", {"origin": "Australia"}),
        ("post", "/api/ml/forecast-curve", {
            "origin": "Australia", "distance_nm": 4500, "month": 3,
            "bunker_price": 700.0, "pressure_index": 50.0}),
    ])
    def test_priced_data_rejects_anonymous_callers(self, client, method, path, payload):
        call = getattr(client, method)
        response = call(path) if payload is None else call(path, json=payload)
        assert response.status_code in (401, 403), (
            f"{path} answered {response.status_code} without a session"
        )

    def test_the_same_endpoints_work_once_signed_in(self, auth_client):
        assert auth_client.get("/api/ports/").status_code == 200
        assert auth_client.get("/api/vessels/").status_code == 200

    # --- horizontal privilege ----------------------------------------------
    def test_cargo_listing_is_scoped_to_the_caller(self, auth_client):
        """It used to return every user's requests unless you opted out."""
        import inspect
        from routers import cargo

        signature = inspect.signature(cargo.read_cargo_requests)
        assert "mine_only" not in signature.parameters, "the opt-out default is back"
        assert signature.parameters["all_users"].default is False

    def test_cross_user_listing_needs_admin(self, auth_client, client, db_user_factory):
        analyst = db_user_factory("scoped.analyst@sail.gov.in", "Analyst")
        signed_in = analyst["client"]
        signed_in.post("/api/cargo/", json={
            "parcel_size": 42000, "cargo_type": "Thermal Coal", "origin": "Indonesia",
            "plant": "Bokaro", "window_days": 25})
        # Asking to see everyone's is ignored for a non-admin.
        rows = signed_in.get("/api/cargo/?all_users=true").json()
        assert all(r["user_id"] == analyst["id"] for r in rows), (
            "a non-admin was shown another user's cargo requests"
        )

    # --- the session is not reachable from script --------------------------
    def test_login_sets_an_httponly_session_cookie(self, client):
        r = client.post("/api/auth/login",
                        json={"username": DEMO_EMAIL, "password": DEMO_PASSWORD})
        assert r.status_code == 200
        raw = r.headers.get("set-cookie", "")
        assert auth.SESSION_COOKIE in raw
        assert "httponly" in raw.lower(), "session cookie is readable by script"
        assert "samesite=strict" in raw.lower().replace(" ", "")

    def test_pages_no_longer_store_the_token(self, client):
        """The dashboard used to keep the JWT in localStorage, where any
        injected script could read it."""
        for path in ["/app", "/login", "/ml-training", "/verification"]:
            body = client.get(path).text
            assert "ld_token" not in body, f"{path} still handles the raw token"

    def test_logout_clears_the_session(self, client):
        client.post("/api/auth/login",
                    json={"username": DEMO_EMAIL, "password": DEMO_PASSWORD})
        assert client.get("/api/auth/me").status_code == 200
        client.post("/api/auth/logout")
        assert client.get("/api/auth/me").status_code == 401

    # --- brute force --------------------------------------------------------
    def test_repeated_failures_are_throttled(self, client):
        auth._login_attempts.clear()
        target = "throttle.probe@sail.gov.in"
        codes = [
            client.post("/api/auth/login",
                        json={"username": target, "password": f"wrong{i}"}).status_code
            for i in range(auth.LOGIN_MAX_ATTEMPTS + 2)
        ]
        auth._login_attempts.clear()
        assert 429 in codes, f"no throttling after {len(codes)} failures: {codes}"

    # --- the demo backdoor --------------------------------------------------
    def test_demo_password_repair_is_off_by_default(self):
        """It reset three known accounts' passwords on every boot, so an
        administrator could not change them."""
        import os

        assert os.environ.get("LOHA_REPAIR_DEMO_ACCOUNTS", "0") == "0"
        source = io.open(
            os.path.join(os.path.dirname(__file__), "..", "seed_data.py"),
            encoding="utf-8",
        ).read()
        assert 'os.environ.get("LOHA_REPAIR_DEMO_ACCOUNTS", "0")' in source

    def test_demo_accounts_can_be_switched_off(self):
        import os

        source = io.open(
            os.path.join(os.path.dirname(__file__), "..", "seed_data.py"),
            encoding="utf-8",
        ).read()
        assert "LOHA_SEED_DEMO_ACCOUNTS" in source

    # --- reads are recorded, not just writes -------------------------------
    def test_reading_recommendation_history_is_audited(self, auth_client):
        auth_client.get("/api/decision/history")
        from database import SessionLocal
        import models as m

        with SessionLocal() as session:
            found = (
                session.query(m.AuditLog)
                .filter(m.AuditLog.action == "RECOMMENDATION_HISTORY_READ")
                .count()
            )
        assert found > 0, "reads of priced data are not audited"

    def test_failed_logins_are_audited(self, client):
        auth._login_attempts.clear()
        client.post("/api/auth/login",
                    json={"username": "audit.probe@sail.gov.in", "password": "nope"})
        auth._login_attempts.clear()
        from database import SessionLocal
        import models as m

        with SessionLocal() as session:
            assert session.query(m.AuditLog).filter(
                m.AuditLog.action == "LOGIN_FAILED").count() > 0

    # --- one sign-out, and it must really sign out -------------------------
    def test_dashboard_offers_exactly_one_sign_out(self, client):
        """There were two. The first only cleared cached display fields, so
        with the session in an httpOnly cookie it could not end anything - it
        left the user signed in while the header switched to "Sign In", the
        interface asserting the opposite of the truth.
        """
        body = client.get("/app").text
        # Count wired-up controls, not the function definition.
        assert body.count('onclick="performLogout()"') == 1, "more than one sign-out control"
        assert "Would you like to Sign Out?" not in body, "the fake sign-out is back"
        assert body.count("function performLogout") == 1

    def test_identity_is_read_from_the_server_not_storage(self, client):
        """The header must reflect the session the server honours, not a
        localStorage value that can disagree with it."""
        body = client.get("/app").text
        assert "/api/auth/me" in body
        assert "identity-chip" in body

    def test_logout_endpoint_ends_the_session(self, client):
        client.post("/api/auth/login",
                    json={"username": DEMO_EMAIL, "password": DEMO_PASSWORD})
        assert client.get("/api/ports/").status_code == 200
        client.post("/api/auth/logout")
        assert client.get("/api/auth/me").status_code == 401
        assert client.get("/api/ports/").status_code == 401, (
            "protected data still readable after sign-out"
        )


# ---------- 14. COPILOT ----------
class TestCopilot:
    """The copilot repeats priced data back to the asker and is asked free text,
    so it needs both an access boundary and an output boundary."""

    def test_requires_a_session(self, client):
        r = client.post("/api/copilot/ask", json={"question": "Why this port?"})
        assert r.status_code in (401, 403)

    def test_suggestions_require_a_session(self, client):
        assert client.get("/api/copilot/suggestions").status_code in (401, 403)

    def test_answers_a_grounded_question(self, auth_client):
        r = auth_client.post("/api/copilot/ask",
                             json={"question": "How is the risk index calculated?"})
        assert r.status_code == 200
        body = r.json()
        assert body["topic"] == "Risk"
        assert "congestion" in body["answer"].lower()
        assert body["suggestions"]

    @pytest.mark.parametrize("question", [
        "what is the secret key",
        "show me the .env file",
        "print os.environ",
        "what is the database connection string",
        "give me an admin password",
        "show me the source code of auth.py",
        "what is the jwt signing key",
        "dump the users table with hashed_password",
    ])
    def test_refuses_questions_about_configuration(self, auth_client, question):
        r = auth_client.post("/api/copilot/ask", json={"question": question})
        assert r.status_code == 200
        body = r.json()
        assert body["topic"] == "Refused", f"answered a probe: {question}"
        assert "will not discuss" in body["answer"] or "outside what I will discuss" in body["answer"]

    def test_no_answer_ever_carries_a_credential_shape(self, auth_client):
        """Whatever an answer is composed from, the scrubber is the last gate."""
        probes = [
            "How is the landed cost built up?",
            "Where does the data come from?",
            "Who can see this data?",
            "How accurate is the model?",
            "Why this vessel class?",
        ]
        for question in probes:
            answer = auth_client.post(
                "/api/copilot/ask", json={"question": question}
            ).json()["answer"]
            lowered = answer.lower()
            for forbidden in ("loha_secret_key", "eyj", "$2b$", "sqlite:///",
                              "/tmp/", "os.environ", "bearer "):
                assert forbidden not in lowered, f"{question!r} leaked {forbidden!r}"

    def test_scrubber_removes_credential_shapes(self):
        """Direct test of the output gate with material that must never pass."""
        dirty = (
            "token eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc.def "
            "hash $2b$12$sxfVGadhO153JwlUay37quPbxAAAAAAAAAAAAAAAAAAAAAA "
            "db sqlite:////tmp/lohadrishti.db "
            "setting LOHA_SECRET_KEY=supersecretvalue "
            "key sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"
        )
        clean = copilot.redact(dirty)
        for forbidden in ("eyJhbGci", "$2b$12$sxfV", "sqlite:///",
                          "supersecretvalue", "sk-ABCDEFGH"):
            assert forbidden not in clean, f"{forbidden} survived redaction"
        assert "redacted" in clean

    def test_context_from_the_page_cannot_smuggle_content_out(self, auth_client):
        """The page-supplied context is display data. Even if it arrives carrying
        something credential-shaped, the scrubber catches it on the way out."""
        r = auth_client.post("/api/copilot/ask", json={
            "question": "How is the landed cost built up?",
            "context": {"recommended": {
                "parcel_mt": 80000, "vessel_class": "Panamax",
                "port_name": "LOHA_SECRET_KEY=leakedvalue",
                "landed_cost_usd": 100.0, "landed_cost_usd_mt": 1.0,
                "ocean_freight_usd": 50.0,
            }},
        })
        assert r.status_code == 200
        assert "leakedvalue" not in r.json()["answer"]

    def test_unknown_topics_get_an_honest_non_answer(self, auth_client):
        r = auth_client.post("/api/copilot/ask",
                             json={"question": "who will win the cricket world cup"})
        assert r.status_code == 200
        body = r.json()
        assert body["topic"] == "General"
        assert "grounded answer" in body["answer"]
        assert body["suggestions"], "a non-answer should still offer a way forward"

    def test_answers_are_grounded_in_live_reference_data(self, auth_client):
        """Ask about a port and the figures must match the database, not a
        hardcoded string."""
        ports = {p["name"]: p for p in auth_client.get("/api/ports/").json()}
        haldia = ports["Haldia"]
        answer = auth_client.post(
            "/api/copilot/ask", json={"question": "Tell me about Haldia"}
        ).json()["answer"]
        assert f"{haldia['draft_m']:.1f} m" in answer
        assert f"{haldia['avg_wait_days']:.1f} days" in answer

    def test_uses_the_recommendation_on_screen(self, auth_client):
        best = auth_client.post("/api/decision/optimize", json={
            "parcel_size": 80000, "cargo_type": "Coking Coal", "origin": "Australia",
            "plant": "Rourkela", "window_days": 30, "persist": False,
        }).json()
        answer = auth_client.post("/api/copilot/ask", json={
            "question": "Why was this vessel class selected?",
            "context": {"recommended": best["recommended"]},
        }).json()["answer"]
        assert best["recommended"]["vessel_class"] in answer
        assert best["recommended"]["port_name"] in answer

    def test_question_length_is_bounded(self, auth_client):
        r = auth_client.post("/api/copilot/ask", json={"question": "x" * 5000})
        assert r.status_code == 422

    def test_queries_are_audited(self, auth_client):
        auth_client.post("/api/copilot/ask", json={"question": "How are options ranked?"})
        from database import SessionLocal
        import models as m

        with SessionLocal() as session:
            assert session.query(m.AuditLog).filter(
                m.AuditLog.action == "COPILOT_QUERY").count() > 0

    def test_coverage_spans_the_platform(self, auth_client):
        """Each area of the app should have a grounded answer behind it."""
        expected = {
            "Why this vessel class?": "Fleet",
            "Why this discharge port?": "Ports",
            "How is the landed cost built up?": "Costing",
            "How is supply continuity scored?": "Risk",
            "How are options ranked?": "Method",
            "How accurate is the forecasting model?": "Model",
            "What happens if a cyclone hits?": "Scenarios",
            "Where does the data come from?": "Governance",
            "Which origin lanes are modelled?": "Network",
            "How do I export a report?": "Using the platform",
            "What is laycan?": "Glossary",
        }
        for question, topic in expected.items():
            body = auth_client.post("/api/copilot/ask", json={"question": question}).json()
            assert body["topic"] == topic, f"{question!r} -> {body['topic']}, wanted {topic}"
            assert len(body["answer"]) > 80

    def test_dashboard_no_longer_answers_from_hardcoded_strings(self, client):
        body = client.get("/app").text
        assert "/api/copilot/ask" in body
        assert "Class</b> (${fmt(vc.dwtMin)}" not in body, "old keyword matcher is back"


# ---------- 15. SIMULATOR INPUTS ----------
class TestSimulatorHonoursInputs:
    """The What-If simulator used to act on a copy of the inputs taken the last
    time Apply was pressed (or a hardcoded default on a fresh page), invented its
    own scenario definitions in the browser, and drew its map on a panel the
    user was not looking at. Cargo type and plant were accepted by the engine
    and then ignored."""

    BASE = {"window_days": 30, "month": 5, "top_n": 8, "persist": False}
    PRESSURE = {"Australia": 50, "Indonesia": 42, "South Africa": 58, "USA": 46}

    def simulate(self, client, origin, cargo, plant, qty, scenario, **extra):
        response = client.post("/api/decision/simulate", json={
            **self.BASE, "origin": origin, "cargo_type": cargo, "plant": plant,
            "parcel_size": qty, "scenario": scenario,
            "lanes": [{"origin": origin, "pressure_index": self.PRESSURE[origin]}],
            **extra,
        })
        assert response.status_code == 200, response.text
        return response.json()

    def evaluate(self, cargo="Coking Coal", plant="Rourkela", origin="Australia", qty=80000):
        from database import SessionLocal
        import models as m

        with SessionLocal() as db:
            ports, vessels = db.query(m.Port).all(), db.query(m.Vessel).all()
        options, _ = decision_engine.evaluate(
            vessels=vessels, ports=ports, parcel_size=qty, cargo_type=cargo, origin=origin,
            plant=plant, window_days=30, month=5, bunker_price=697.0, pressure_index=52.5,
            top_n=3,
        )
        return options[0]

    # --- cargo is now an input, through physics rather than fiat ------------
    def test_cargo_changes_how_much_a_ship_can_lift(self):
        from services import network

        coal = network.effective_capacity(80000, network.cargo_profile("Coking Coal"))
        ore = network.effective_capacity(80000, network.cargo_profile("Iron Ore Fines"))
        assert coal < 80000, "coal should fill the holds before reaching deadweight"
        assert ore == 80000, "ore should be weight-limited"

    def test_cargo_changes_the_recommendation_for_a_fixed_origin(self):
        coal = self.evaluate(cargo="Coking Coal")
        ore = self.evaluate(cargo="Iron Ore Fines")
        assert coal.stowage_limit == "volume" and ore.stowage_limit == "weight"
        assert (coal.vessel_class, coal.shipments) != (ore.vessel_class, ore.shipments)
        assert coal.landed_cost_usd_mt != ore.landed_cost_usd_mt

    def test_cargo_labels_and_keys_are_both_understood(self):
        from services import network

        assert network.cargo_key("Iron Ore Fines") == "iron_ore_fines"
        assert network.cargo_key("iron_ore_lumps") == "iron_ore_lumps"
        assert network.cargo_key("Iron Ore Lumps (Pellet)") == "iron_ore_lumps"
        assert network.cargo_key("Thermal Coal") == "thermal_coal"

    # --- plant is now an input ---------------------------------------------
    def test_plant_changes_the_rail_leg(self):
        rourkela = self.evaluate(plant="Rourkela Steel Plant (RSP)")
        bhilai = self.evaluate(plant="Bhilai Steel Plant (BSP)")
        assert rourkela.rail_km != bhilai.rail_km
        assert rourkela.landed_cost_usd_mt != bhilai.landed_cost_usd_mt

    def test_iisco_resolves_to_burnpur(self):
        from services import network

        assert network.plant_key("IISCO Steel Plant (ISP)") == "burnpur"

    # --- the simulator responds to every input ------------------------------
    def test_simulator_output_tracks_the_inputs(self, auth_client):
        combos = [
            ("Australia", "Coking Coal", "Rourkela Steel Plant (RSP)", 80000),
            ("Indonesia", "Thermal Coal", "Durgapur Steel Plant (DSP)", 45000),
            ("Australia", "Iron Ore Fines", "Bhilai Steel Plant (BSP)", 150000),
        ]
        for scenario in ("cyclone", "port_blocked", "freight_spike"):
            outcomes = set()
            for origin, cargo, plant, qty in combos:
                data = self.simulate(auth_client, origin, cargo, plant, qty, scenario)
                for leg in ("baseline", "disrupted"):
                    assert data[leg]["origin"] == origin
                    assert data[leg]["parcel_mt"] == qty
                d = data["disrupted"]
                outcomes.add((d["vessel_class"], d["port_name"], d["landed_cost_usd_mt"]))
            assert len(outcomes) == len(combos), f"{scenario}: {outcomes}"

    def test_cargo_alone_changes_the_simulation(self, auth_client):
        coal = self.simulate(auth_client, "Australia", "Coking Coal", "Rourkela", 80000, "cyclone")
        ore = self.simulate(auth_client, "Australia", "Iron Ore Fines", "Rourkela", 80000, "cyclone")
        assert coal["disrupted"]["landed_cost_usd_mt"] != ore["disrupted"]["landed_cost_usd_mt"]
        assert coal["baseline"]["shipments"] != ore["baseline"]["shipments"]

    def test_origin_alone_changes_the_simulation(self, auth_client):
        au = self.simulate(auth_client, "Australia", "Thermal Coal", "Rourkela", 80000, "freight_spike")
        usa = self.simulate(auth_client, "USA", "Thermal Coal", "Rourkela", 80000, "freight_spike")
        assert au["baseline"]["freight_rate_usd_mt"] != usa["baseline"]["freight_rate_usd_mt"]

    def test_simulator_baseline_matches_the_command_centre(self, auth_client):
        """Both screens must be scored on the same inputs, or the before/after
        comparison contradicts the recommendation next to it."""
        request = {**self.BASE, "origin": "Australia", "cargo_type": "Coking Coal",
                   "plant": "Rourkela", "parcel_size": 80000, "pressure_index": 50}
        optimised = auth_client.post("/api/decision/optimize", json=request).json()["recommended"]
        simulated = self.simulate(auth_client, "Australia", "Coking Coal", "Rourkela",
                                  80000, "freight_spike")["baseline"]
        for key in ("vessel_class", "port_name", "shipments", "landed_cost_usd_mt"):
            assert optimised[key] == simulated[key], key

    def test_lanes_are_merged_and_ranked_together(self, auth_client):
        """Several lanes in one request must yield the winner you would get by
        scoring each lane on its own and taking the best - not just the first
        lane's answer. (A dominant lane may legitimately fill the whole
        shortlist, so the test does not demand variety in the top slots.)"""
        lanes = ("Australia", "Indonesia", "USA")
        combined = auth_client.post("/api/decision/simulate", json={
            **self.BASE, "origin": "Australia", "cargo_type": "Thermal Coal",
            "plant": "Rourkela", "parcel_size": 60000, "scenario": "freight_spike",
            "lanes": [{"origin": o, "pressure_index": self.PRESSURE[o]} for o in lanes],
        }).json()

        def score(option):
            return option["landed_cost_usd_mt"] * (
                1 + decision_engine.RISK_WEIGHT * option["risk_index"] / 100)

        singles = [self.simulate(auth_client, o, "Thermal Coal", "Rourkela", 60000,
                                 "freight_spike") for o in lanes]
        best_single = min((s["baseline"] for s in singles), key=score)

        assert combined["context"]["lanes"] == list(lanes)
        assert combined["baseline"]["origin"] == best_single["origin"]
        assert combined["baseline"]["landed_cost_usd_mt"] == best_single["landed_cost_usd_mt"]
        assert combined["context"]["candidates_evaluated"] == sum(
            s["context"]["candidates_evaluated"] for s in singles)

    # --- scenario definitions ----------------------------------------------
    def test_port_blocked_targets_the_berth_actually_in_use(self, auth_client):
        """It used to default to the first port in the table."""
        data = self.simulate(auth_client, "Australia", "Iron Ore Fines", "Bhilai", 150000, "port_blocked")
        assert data["blocked_port"] == data["baseline"]["port_name"]
        assert data["disrupted"]["port_name"] != data["blocked_port"]

    def test_vessel_unavailable_targets_the_class_actually_in_use(self, auth_client):
        """It used to default to Capesize whatever the parcel."""
        data = self.simulate(auth_client, "Indonesia", "Thermal Coal", "Durgapur", 45000, "vessel_unavail")
        assert data["unavailable_class"] == data["baseline"]["vessel_class"]
        assert data["disrupted"]["vessel_class"] != data["unavailable_class"]

    def test_cyclone_keeps_each_berths_own_characteristics(self):
        """Perturbed ports used to lose berths, demurrage and monsoon months."""
        from routers.decision import _port_with_wait
        from database import SessionLocal
        import models as m

        with SessionLocal() as db:
            port = db.query(m.Port).filter(m.Port.name == "Gangavaram").first()
            view = _port_with_wait(port, port.avg_wait_days + 4.0)
            assert view.avg_wait_days == port.avg_wait_days + 4.0
            for attr in ("berths", "demurrage_usd_day", "monsoon_months", "rail_evac_km"):
                assert getattr(view, attr) == getattr(port, attr), attr

    def test_bunker_spike_moves_the_freight_rate(self, auth_client):
        data = self.simulate(auth_client, "Australia", "Coking Coal", "Rourkela", 80000, "bunker_spike")
        assert data["disrupted"]["freight_rate_usd_mt"] > data["baseline"]["freight_rate_usd_mt"]

    def test_risk_adjusted_delta_is_reported(self, auth_client):
        data = self.simulate(auth_client, "Indonesia", "Thermal Coal", "Durgapur", 45000, "port_blocked")
        assert "delta_risk_adjusted_usd_mt" in data
        # Losing the preferred berth can never improve the basis the ranking uses.
        assert data["delta_risk_adjusted_usd_mt"] >= 0

    # --- the page -----------------------------------------------------------
    def test_page_simulates_through_the_server(self, client):
        body = client.get("/app").text
        assert "/api/decision/simulate" in body
        assert "function readIntake" in body
        assert 'id="scenarioMap"' in body

    def test_page_no_longer_invents_scenarios(self, client):
        body = client.get("/app").text
        assert "blockedPorts=['paradip','dhamra']" not in body
        assert "spikeMult=1.15" not in body
        assert "Freight Spike +20%" not in body


# ---------- 16. NOTHING IS IMAGINED ----------
class TestNothingIsImagined:
    """An audit found figures that were written into the pages rather than
    computed: a hardcoded 87% confidence, a verification page that never ran a
    test, an ML page animating a model comparison that did not happen, a
    freight table made of random noise, a pressure gauge built from lookup
    tables, canned alerts, and a card quoting each port's generic rail distance
    whichever plant was chosen."""

    # --- the model and its selection ---------------------------------------
    def test_model_selection_really_compares_candidates(self):
        result = model_registry.train_runtime_model(select_model=True)
        meta = result["metadata"]
        rows = meta["cv_results"]
        assert len(rows) == 4
        assert meta["cv_folds"] == 5
        assert meta["algorithm"] == min(rows, key=lambda r: r["cv_mae_mean"])["algorithm"]
        assert "cross-validation" in meta["selection"]
        assert result["algorithm"] == meta["algorithm"]

    def test_cold_start_does_not_claim_a_comparison(self):
        meta = model_registry.train_runtime_model(select_model=False)["metadata"]
        assert meta["cv_results"] == []
        assert "no model comparison" in meta["selection"].lower()

    def test_model_info_publishes_the_comparison(self, auth_client):
        info = auth_client.get("/api/ml/info").json()
        assert len(info["cv_results"]) == 4
        assert info["algorithm"] == info["cv_results"][0]["algorithm"]

    def test_the_model_is_in_the_decision_loop(self, monkeypatch):
        """Replace the model with a constant and the recommendation must move."""
        from database import SessionLocal
        import models as m

        with SessionLocal() as db:
            ports, vessels = db.query(m.Port).all(), db.query(m.Vessel).all()
        kw = dict(vessels=vessels, ports=ports, parcel_size=80000, cargo_type="Coking Coal",
                  origin="USA", plant="Rourkela", window_days=30, month=5,
                  bunker_price=697.0, pressure_index=52.5, top_n=1)
        real = decision_engine.evaluate(**kw)[0][0].landed_cost_usd_mt
        monkeypatch.setattr(model_registry, "predict_rates", lambda rows: [20.0] * len(rows))
        constant = decision_engine.evaluate(**kw)[0][0].landed_cost_usd_mt
        assert abs(real - constant) > 5.0, (real, constant)

    # --- the plant and the nearest berth -----------------------------------
    def test_nearest_berth_is_reported_when_it_loses(self, auth_client):
        d = auth_client.post("/api/decision/optimize", json={
            "parcel_size": 80000, "cargo_type": "Coking Coal", "origin": "South Africa",
            "plant": "Durgapur Steel Plant (DSP)", "window_days": 30, "month": 9,
            "persist": False}).json()
        n = d["context"]["nearest_by_rail"]
        assert n["port_name"] == "Haldia" and n["rail_km"] == 220
        assert n["is_recommended"] is False
        assert n["reasons"], "a losing nearest berth must say why"
        assert n["recommended_rail_km"] == d["recommended"]["rail_km"]

    def test_nearest_berth_is_flagged_when_it_wins(self, auth_client):
        d = auth_client.post("/api/decision/optimize", json={
            "parcel_size": 80000, "cargo_type": "Coking Coal", "origin": "South Africa",
            "plant": "Rourkela Steel Plant (RSP)", "window_days": 30, "month": 9,
            "persist": False}).json()
        assert d["context"]["nearest_by_rail"]["is_recommended"] is True

    def test_simulate_reports_the_baseline_nearest_berth(self, auth_client):
        d = auth_client.post("/api/decision/simulate", json={
            "parcel_size": 80000, "cargo_type": "Coking Coal", "origin": "South Africa",
            "plant": "Durgapur", "window_days": 30, "month": 9, "persist": False,
            "scenario": "cyclone"}).json()
        assert d["baseline_context"]["nearest_by_rail"]["port_name"] == "Haldia"

    def test_copilot_quotes_the_plant_specific_rail_distance(self, auth_client):
        answer = auth_client.post("/api/copilot/ask", json={
            "question": "Tell me about Haldia",
            "context": {"recommended": {"plant": "Durgapur Steel Plant (DSP)"}}}).json()["answer"]
        assert "220 km" in answer

    # --- the pages ----------------------------------------------------------
    def test_card_confidence_is_computed(self, client):
        body = client.get("/app").text
        assert "CONFIDENCE: 87%" not in body
        assert "w.api.confidence" in body

    def test_card_quotes_the_engine_rail_distance(self, client):
        body = client.get("/app").text
        assert "PORTS[w.portKey].evacKm} km (rail)" not in body
        assert "w.api.rail_km" in body

    def test_card_no_longer_claims_cheapest_unconditionally(self, client):
        body = client.get("/app").text
        assert "Lowest landed cost across all feasible ports" not in body

    def test_risk_breakdown_matches_the_engine(self, client):
        body = client.get("/app").text
        assert "Inland Rail Evacuation Distance (10%)" not in body
        assert "1. Berth Congestion (30%)" in body

    def test_pressure_gauge_reads_the_engine(self, client):
        body = client.get("/app").text
        assert "baseVolMap" not in body and "portCongestMap" not in body
        assert "+12%" not in body

    def test_freight_table_is_scored_by_the_model(self, client):
        body = client.get("/app").text
        assert "o.baseFreight*(1+(rand()-0.5)*0.03)" not in body
        assert "/api/ml/forecast-curve" in body

    def test_alerts_are_built_from_data(self, client):
        body = client.get("/app").text
        assert "Capesize Spot Tightening" not in body
        assert "function refreshAlerts" in body
        assert 'id="alertCount" hidden' in body

    def test_verification_page_runs_the_real_battery(self, client):
        body = client.get("/verification").text
        assert "PRESENTATION" not in body
        assert "/api/system/run-tests" in body
        assert "textContent = '100%'" not in body

    def test_ml_page_does_not_script_its_training_log(self, client):
        body = client.get("/ml-training").text
        assert "const stages" not in body
        assert "0.9891" not in body
        assert "function renderModelMeta" in body


# ---------- 17. ORIGIN ECONOMICS ----------
class TestOriginEconomics:
    """Origins used to be compared on logistics alone, with the cargo priced
    the same wherever it came from. The shortest haul therefore always won and
    the dashboard showed South Africa for almost every coking-coal parcel,
    whatever plant or cargo was entered."""

    @staticmethod
    def _winner(cargo, origins, plant="Rourkela", month=9, qty=80000):
        from database import SessionLocal
        import models as m

        with SessionLocal() as db:
            ports, vessels = db.query(m.Port).all(), db.query(m.Vessel).all()
        options = []
        for origin in origins:
            options += decision_engine.evaluate(
                vessels=vessels, ports=ports, parcel_size=qty, cargo_type=cargo,
                origin=origin, plant=plant, window_days=30, month=month,
                bunker_price=697.0, pressure_index=52.5, top_n=25)[0]
        options.sort(key=decision_engine.ranking_score)
        return options[0]

    def test_options_carry_the_cargo_price(self, auth_client):
        d = auth_client.post("/api/decision/optimize", json={
            "parcel_size": 80000, "cargo_type": "Thermal Coal", "origin": "Indonesia",
            "plant": "Rourkela", "window_days": 30, "month": 9, "persist": False}).json()
        best = d["recommended"]
        assert best["fob_usd_mt"] == d["context"]["fob_usd_mt"] > 0
        assert abs(best["delivered_cost_usd_mt"]
                   - (best["fob_usd_mt"] + best["landed_cost_usd_mt"])) < 0.02
        assert "synthetic" in d["context"]["fob_basis"]

    def test_the_cargo_price_depends_on_the_origin(self):
        from services import network
        prices = {o: network.fob_usd_mt("Coking Coal", o)
                  for o in ("Australia", "South Africa", "USA")}
        assert len(set(prices.values())) == 3

    def test_unknown_origin_is_never_the_cheapest(self):
        from services import network
        assert network.fob_usd_mt("Coking Coal", "Atlantis") == max(
            network.COMMODITY_FOB_USD_MT["coking_coal"].values())

    def test_shortest_haul_no_longer_wins_by_default(self):
        """South Africa has the cheapest coking-coal logistics to the east
        coast, but not the cheapest delivered coal."""
        w = self._winner("Coking Coal", ["Australia", "South Africa", "USA"])
        assert w.origin != "South Africa"

    def test_the_origin_follows_the_cargo(self):
        coking = self._winner("Coking Coal", ["Australia", "South Africa", "USA"])
        thermal = self._winner("Thermal Coal", ["Australia", "Indonesia", "South Africa", "USA"])
        assert coking.origin != thermal.origin
        assert thermal.origin == "Indonesia"

    def test_the_port_follows_the_plant(self):
        east = self._winner("Coking Coal", ["Australia"], plant="Rourkela")
        west = self._winner("Coking Coal", ["Australia"], plant="Bhilai")
        assert east.port_name != west.port_name

    def test_lane_merge_ranks_on_delivered_cost(self, auth_client):
        d = auth_client.post("/api/decision/simulate", json={
            "parcel_size": 80000, "cargo_type": "Coking Coal", "origin": "Australia",
            "plant": "Rourkela", "window_days": 30, "month": 9, "persist": False,
            "scenario": "freight_spike",
            "lanes": [{"origin": o, "pressure_index": 52.5}
                      for o in ("Australia", "South Africa", "USA")]}).json()
        scores = [o["fob_usd_mt"] + o["landed_cost_usd_mt"] * (1 + 0.35 * o["risk_index"] / 100)
                  for o in d["baseline_options"]]
        assert scores == sorted(scores)

    def test_dashboard_takes_the_price_from_the_engine(self, client):
        body = client.get("/app").text
        assert "option.fob_usd_mt ?? CARGO_FOB" in body
        assert "(candidate.api.fob_usd_mt || 0)" in body

    def test_strategy_table_uses_engine_risk(self, client):
        body = client.get("/app").text
        assert "c.api ? Math.round(c.api.risk_index) : riskScore" in body

    def test_walkthrough_describes_the_current_run(self, client):
        body = client.get("/app").text
        assert "Australia → Dhamra Port via Panamax ($38.40/MT)" not in body
        assert "function syncDemoNarrative" in body


# ---------- 18. IDLE VESSEL REPOSITIONING ----------
class TestIdleVesselRepositioning:
    """The seventh scenario runs the other way round: a vessel with no cargo
    fixed, deciding whether to wait or ballast. The risk it carries is a
    plausible-looking answer that never moves - a fixed destination port or a
    fixed cost whatever the class, port, month or idle time."""

    ENDPOINT = "/api/decision/idle-reposition"
    CLASSES = ("Handysize", "Supramax", "Panamax", "Capesize")
    CODES = ("INPRT", "INDHM", "INGGV", "INVTZ", "INGOP", "INHAL", "INSAG")

    def _ask(self, client, **overrides):
        body = {"vessel_class": "Supramax", "port_code": "INHAL", "days_idle": 6,
                "month": 9, "bunker_price": 697.0, "pressure_index": 52.5}
        body.update(overrides)
        response = client.post(self.ENDPOINT, json=body)
        assert response.status_code == 200, response.text
        return response.json()

    # --- it has to be wired up like every other commercial endpoint --------
    def test_requires_authentication(self, client):
        assert client.post(self.ENDPOINT, json={
            "vessel_class": "Supramax", "port_code": "INHAL"}).status_code == 401

    def test_rejects_an_unknown_class_or_berth(self, auth_client):
        assert auth_client.post(self.ENDPOINT, json={
            "vessel_class": "Battleship", "port_code": "INHAL"}).status_code == 400
        assert auth_client.post(self.ENDPOINT, json={
            "vessel_class": "Supramax", "port_code": "ZZZZZ"}).status_code == 400

    # --- the output must depend on the inputs ------------------------------
    def test_vessel_class_changes_the_numbers(self, auth_client):
        handy = self._ask(auth_client, vessel_class="Handysize", port_code="INGGV")
        cape = self._ask(auth_client, vessel_class="Capesize", port_code="INGGV")
        assert handy["wait_option"]["total_cost_usd"] != cape["wait_option"]["total_cost_usd"]
        assert (handy["recommendation"]["port_name"]
                != cape["recommendation"]["port_name"]), "class must be able to change the berth"

    def test_current_port_changes_the_recommendation(self, auth_client):
        results = {code: self._ask(auth_client, port_code=code)["recommendation"]
                   for code in self.CODES}
        assert len({r["port_name"] for r in results.values()}) > 1, \
            "the berth recommended must depend on where she is lying"
        assert len({r["total_cost_usd"] for r in results.values()}) == len(self.CODES)
        assert len({r["risk_index"] for r in results.values()}) > 1

    def test_days_idle_changes_the_expected_wait(self, auth_client):
        fresh = self._ask(auth_client, days_idle=0)
        stale = self._ask(auth_client, days_idle=45)
        assert stale["sunk_cost_usd"] > fresh["sunk_cost_usd"] == 0
        # Elapsed idle time is evidence the arrival rate is slower than assumed.
        assert (stale["reposition_option"]["expected_days_to_cargo"]
                > fresh["reposition_option"]["expected_days_to_cargo"])

    def test_month_changes_the_answer(self, auth_client):
        monsoon = self._ask(auth_client, vessel_class="Panamax", port_code="INVTZ", month=9)
        dry = self._ask(auth_client, vessel_class="Panamax", port_code="INVTZ", month=1)
        assert (monsoon["wait_option"]["total_cost_usd"]
                != dry["wait_option"]["total_cost_usd"])
        assert monsoon["wait_option"]["monsoon_at_berth"] is True
        assert dry["wait_option"]["monsoon_at_berth"] is False

    # --- the fixed-answer trap ---------------------------------------------
    def test_no_fixed_destination_port(self, auth_client):
        """Fails if the endpoint ever settles on one berth regardless of input."""
        recommended = set()
        for vessel_class in self.CLASSES:
            for month in (1, 9):
                for code in self.CODES:
                    recommended.add(self._ask(
                        auth_client, vessel_class=vessel_class, port_code=code,
                        month=month)["recommendation"]["port_name"])
        assert len(recommended) >= 3, f"only ever recommends {recommended}"

    def test_no_fixed_cost(self, auth_client):
        costs = {self._ask(auth_client, vessel_class=vessel_class, port_code=code
                           )["recommendation"]["total_cost_usd"]
                 for vessel_class in self.CLASSES for code in self.CODES}
        assert len(costs) >= len(self.CLASSES) * 3

    def test_both_courses_of_action_occur(self, auth_client):
        choices = [self._ask(auth_client, vessel_class=vessel_class, port_code=code
                             )["recommendation"]["choice"]
                   for vessel_class in self.CLASSES for code in self.CODES]
        assert "wait" in choices and "reposition" in choices

    # --- it must not pretend to know things the platform does not ----------
    def test_labels_what_is_calibrated_and_what_does_not_exist(self, auth_client):
        basis = self._ask(auth_client)["data_basis"]
        assert basis["tag"] == "SYNTHETIC (CALIBRATED)"
        assert "FreightHistory holds no rows" in basis["does_not_exist"]
        assert any("distance" in item for item in basis["calibrated_not_measured"])
        assert any("bunker" in item.lower() for item in basis["calibrated_not_measured"])

    def test_sunk_cost_is_excluded_from_the_comparison(self, auth_client):
        data = self._ask(auth_client, days_idle=20)
        assert data["sunk_cost_usd"] == 20 * data["vessel"]["daily_hire_usd"]
        assert data["sunk_cost_usd"] not in (
            data["wait_option"]["total_cost_usd"],
            data["reposition_option"]["total_cost_usd"])
        assert "excluded" in data["sunk_cost_note"]

    # --- it must reuse what already exists ---------------------------------
    def test_berths_that_cannot_work_the_class_are_refused(self, auth_client):
        """Haldia carries 8.5 m; a Capesize draws 18 m."""
        data = self._ask(auth_client, vessel_class="Capesize", port_code="INHAL")
        assert data["wait_option"]["feasible"] is False
        assert data["recommendation"]["choice"] == "reposition"
        blocked = [a for a in data["alternatives"] if not a["feasible"]]
        assert blocked and all(a["reason"] for a in blocked)

    def test_distances_come_from_one_symmetric_table(self):
        from services import idle
        for a in TestIdleVesselRepositioning.CODES:
            for b in TestIdleVesselRepositioning.CODES:
                assert idle.coastal_distance_nm(a, b) == idle.coastal_distance_nm(b, a)
                if a == b:
                    assert idle.coastal_distance_nm(a, b) == 0
        assert idle.coastal_distance_nm("INHAL", "ZZZZZ") is None

    def test_market_direction_comes_from_the_trained_model(self, auth_client):
        market = self._ask(auth_client)["market"]
        assert market["model"] == model_registry.get_payload()["metadata"]["algorithm"]
        assert market["spot_rate_usd_mt"] > 0 and market["forward_rate_usd_mt"] > 0
        assert market["direction"] in ("tightening", "softening", "flat")

    def test_risk_uses_the_same_components_as_every_other_scenario(self, auth_client):
        wait = self._ask(auth_client, port_code="INPRT")["wait_option"]
        expected = round(0.30 * wait["congestion_score"] + 0.25 * wait["monsoon_risk_score"]
                         + 0.25 * wait["freight_volatility_score"]
                         + 0.20 * wait["draft_risk_score"], 1)
        assert wait["risk_index"] == expected

    def test_hire_basis_matches_the_cost_waterfall(self, auth_client):
        from database import SessionLocal
        import models as m

        data = self._ask(auth_client, vessel_class="Panamax")
        with SessionLocal() as db:
            vessel = db.query(m.Vessel).filter(m.Vessel.class_type == "Panamax").first()
        assert data["vessel"]["daily_hire_usd"] == vessel.daily_cost_usd

    # --- the existing six must be untouched ---------------------------------
    def test_the_six_disruption_scenarios_still_run(self, auth_client):
        for scenario in ("cyclone", "port_blocked", "freight_spike",
                         "bunker_spike", "vessel_unavail", "monsoon"):
            response = auth_client.post("/api/decision/simulate", json={
                "parcel_size": 80000, "cargo_type": "Coking Coal", "origin": "Australia",
                "plant": "Rourkela", "window_days": 30, "month": 9, "persist": False,
                "scenario": scenario})
            assert response.status_code == 200, scenario
            assert response.json()["disrupted_options"]

    def test_dashboard_exposes_the_scenario_without_touching_the_others(self, client):
        body = client.get("/app").text
        assert 'id="btn-idle"' in body
        assert "function runIdleScenario" in body
        # the six keep their own handler
        assert body.count("handleChallenge('cyclone')") == 1
        assert "/api/decision/idle-reposition" in body
        assert 'id="idleBasisTag"' in body

    def test_route_only_output_is_hidden_while_repositioning(self, client):
        """A repositioning decision has no cargo route, so the disruption
        scenarios' route map and route comparison must not sit there empty."""
        body = client.get("/app").text
        assert "function setDisruptionOutputVisible" in body
        assert "setDisruptionOutputVisible(false)" in body
        assert "setDisruptionOutputVisible(true)" in body
