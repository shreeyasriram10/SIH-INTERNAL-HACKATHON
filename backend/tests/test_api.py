import os
import sys
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app  # noqa: E402
from services import decision_engine, model_registry, rate_horizon  # noqa: E402

DEMO_EMAIL = "admin@sail.gov.in"
DEMO_PASSWORD = "12345"


@pytest.fixture(scope="session")
def client():
    # The context manager runs the lifespan hook, which creates the schema and
    # seeds reference data - the API tests depend on both.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session", autouse=True)
def ensure_model():
    """Make sure a usable model exists before any test asks for a prediction."""
    model_registry.get_payload()


@pytest.fixture(scope="session")
def auth_headers(client):
    response = client.post(
        "/api/auth/login",
        json={"username": DEMO_EMAIL, "password": DEMO_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


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
        assert "Command Center" in r.text

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
    def test_ports_seeded(self, client):
        r = client.get("/api/ports/")
        assert r.status_code == 200
        ports = r.json()
        assert len(ports) >= 5
        assert {"Paradip", "Dhamra", "Haldia"} <= {p["name"] for p in ports}
        for port in ports:
            assert port["draft_m"] > 0
            assert port["mech_rate_mt_d"] > 0

    def test_vessels_seeded(self, client):
        r = client.get("/api/vessels/")
        assert r.status_code == 200
        classes = {v["class_type"] for v in r.json()}
        assert {"Handysize", "Supramax", "Panamax", "Capesize"} <= classes


# ---------- 5. ML PIPELINE ----------
class TestMLPipeline:
    def test_ml_info(self, client):
        r = client.get("/api/ml/info")
        assert r.status_code == 200
        data = r.json()
        assert data["r2_score"] > 0.90
        assert data["mae_usd"] > 0

    def test_ml_prediction(self, client):
        r = client.post(
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

    def test_ml_prediction_rejects_bad_input(self, client):
        r = client.post(
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

    def test_forecast_curve(self, client):
        r = client.post(
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

    def test_optimize_returns_ranked_options(self, client):
        r = client.post("/api/decision/optimize", json=self.BASE_REQUEST)
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

    def test_cost_components_sum_to_the_total(self, client):
        r = client.post("/api/decision/optimize", json=self.BASE_REQUEST)
        for option in r.json()["options"]:
            parts = (
                option["ocean_freight_usd"] + option["deadfreight_usd"]
                + option["vessel_hire_usd"] + option["port_dues_usd"]
                + option["demurrage_usd"] + option["lightering_usd"]
                + option["inland_rail_usd"]
            )
            assert parts == pytest.approx(option["landed_cost_usd"], rel=1e-6)

    def test_explanation_is_populated(self, client):
        r = client.post("/api/decision/optimize", json=self.BASE_REQUEST)
        assert len(r.json()["recommended"]["explanation"]) > 40

    def test_small_parcel_picks_a_small_ship(self, client):
        r = client.post(
            "/api/decision/optimize", json={**self.BASE_REQUEST, "parcel_size": 35000}
        )
        best = r.json()["recommended"]
        assert best["vessel_class"] == "Handysize"
        assert best["utilisation_pct"] > 80

    def test_large_parcel_picks_a_large_ship(self, client):
        r = client.post(
            "/api/decision/optimize", json={**self.BASE_REQUEST, "parcel_size": 170000}
        )
        assert r.json()["recommended"]["vessel_class"] == "Capesize"

    def test_monsoon_month_raises_risk(self, client):
        dry = client.post("/api/decision/optimize", json={**self.BASE_REQUEST, "month": 2})
        wet = client.post("/api/decision/optimize", json={**self.BASE_REQUEST, "month": 7})
        assert wet.json()["recommended"]["risk_index"] > dry.json()["recommended"]["risk_index"]

    def test_invalid_parcel_is_rejected(self, client):
        r = client.post("/api/decision/optimize", json={**self.BASE_REQUEST, "parcel_size": 0})
        assert r.status_code == 422

    def test_optimize_persists_a_recommendation(self, client, auth_headers):
        before = client.get("/api/decision/history", headers=auth_headers).json()["count"]
        client.post(
            "/api/decision/optimize",
            json={**self.BASE_REQUEST, "persist": True},
            headers=auth_headers,
        )
        after = client.get("/api/decision/history", headers=auth_headers).json()["count"]
        assert after > before

    def test_port_blocked_scenario_diverts(self, client):
        r = client.post(
            "/api/decision/simulate",
            json={**self.BASE_REQUEST, "scenario": "port_blocked", "blocked_port": "Dhamra"},
        )
        assert r.status_code == 200
        assert r.json()["disrupted"]["port_name"] != "Dhamra"

    def test_bunker_spike_costs_more(self, client):
        r = client.post(
            "/api/decision/simulate", json={**self.BASE_REQUEST, "scenario": "bunker_spike"}
        )
        assert r.status_code == 200
        assert r.json()["delta_usd"] > 0

    def test_vessel_unavailable_scenario_switches_class(self, client):
        r = client.post(
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
    def test_system_status(self, client):
        r = client.get("/api/system/status")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "OPERATIONAL"
        assert data["database"]["status"] == "Connected"

    def test_live_system_tests(self, client):
        r = client.get("/api/system/run-tests")
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
    def test_endpoint_anchors_to_the_server_clock(self, client):
        r = client.post(
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

    def test_endpoint_rejects_an_out_of_range_horizon(self, client):
        r = client.post(
            "/api/ml/rate-horizon", json={"origin": "Australia", "horizon_days": 5000}
        )
        assert r.status_code == 422
