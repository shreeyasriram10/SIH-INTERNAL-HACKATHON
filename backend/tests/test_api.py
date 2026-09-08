import io
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

    def test_supply_continuity_does_not_saturate(self, client):
        """The score used to be `50 + slack x 100` clamped to 100, so any cycle
        shorter than half the window read a flat 100/100 - a delivery guarantee
        no charter can offer. It must stay below the ceiling and vary."""
        scores = []
        for origin in ("Australia", "Indonesia", "South Africa", "USA"):
            for window in (20, 30, 45):
                r = client.post("/api/decision/optimize", json={
                    **self.BASE_REQUEST, "origin": origin, "window_days": window,
                })
                if r.status_code != 200:
                    continue
                best = r.json()["recommended"]
                scores.append(best["supply_continuity"])
                assert 0 < best["supply_continuity"] < 100, best["supply_continuity"]

        assert len(scores) >= 8
        assert len(set(scores)) > len(scores) // 2, "score barely discriminates"

    def test_supply_continuity_falls_as_risk_rises(self, client):
        """A calm month and a cyclone month must not score the same."""
        calm = client.post("/api/decision/optimize",
                           json={**self.BASE_REQUEST, "month": 2}).json()["recommended"]
        rough = client.post("/api/decision/optimize",
                            json={**self.BASE_REQUEST, "month": 7}).json()["recommended"]
        assert rough["risk_index"] > calm["risk_index"]
        assert rough["supply_continuity"] < calm["supply_continuity"]

    def test_supply_continuity_falls_as_the_window_tightens(self, client):
        roomy = client.post("/api/decision/optimize",
                            json={**self.BASE_REQUEST, "window_days": 60}).json()["recommended"]
        tight = client.post("/api/decision/optimize",
                            json={**self.BASE_REQUEST, "window_days": 18}).json()["recommended"]
        assert tight["supply_continuity"] < roomy["supply_continuity"]

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
        """Compare the newest row rather than a page count - /history returns a
        capped page, so once it is full the count stops moving."""
        def newest_id():
            page = client.get(
                "/api/decision/history?limit=1", headers=auth_headers
            ).json()["items"]
            return page[0]["id"] if page else None

        before = newest_id()
        client.post(
            "/api/decision/optimize",
            json={**self.BASE_REQUEST, "persist": True},
            headers=auth_headers,
        )
        after = newest_id()
        assert after is not None
        assert after != before

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

    def _totals(self, client, **overrides):
        response = client.post(
            "/api/decision/optimize", json={**self.REQUEST, **overrides}
        )
        assert response.status_code == 200
        return sorted(o["landed_cost_usd_mt"] for o in response.json()["options"])

    def test_runner_up_can_be_indistinguishable_from_the_winner(self, client):
        """Documents why the runner-up is a useless comparator."""
        totals = self._totals(client)
        assert len(totals) >= 2
        assert totals[1] - totals[0] < 1.0, (
            "top two are far apart here; if this ever holds broadly the saving "
            "metric could go back to comparing against the runner-up"
        )

    def test_median_gives_a_material_saving(self, client):
        totals = self._totals(client)
        median = totals[len(totals) // 2]
        saving = median - totals[0]
        assert saving > 0.5, f"saving vs median is only ${saving:.2f}/MT"

    def test_shortlist_spread_is_wide_enough_to_be_worth_optimising(self, client):
        totals = self._totals(client)
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

    def _score(self, client, **overrides):
        response = client.post(
            "/api/decision/optimize", json={**self.REQUEST, **overrides}
        )
        assert response.status_code == 200
        return response.json()["recommended"]

    def test_a_tighter_window_lowers_continuity(self, client):
        tight = self._score(client, window_days=15)["supply_continuity"]
        roomy = self._score(client, window_days=60)["supply_continuity"]
        assert tight < roomy, f"{tight} not below {roomy}"

    def test_continuity_spans_a_useful_range(self, client):
        """A score that barely moves reads as broken even when it is computed."""
        scores = {
            self._score(client, window_days=days)["supply_continuity"]
            for days in (12, 15, 20, 30, 45, 60, 90)
        }
        assert len(scores) >= 5, f"only {len(scores)} distinct values: {scores}"
        assert max(scores) - min(scores) > 25

    def test_factors_are_returned_so_the_score_can_be_explained(self, client):
        """The card names the binding factor; it needs all three to do that."""
        best = self._score(client, window_days=30)
        for field in (
            "schedule_headroom_pct",
            "continuity_risk_factor_pct",
            "execution_factor_pct",
        ):
            assert field in best, f"missing {field}"
            assert 0 <= best[field] <= 100

    def test_continuity_never_claims_certainty(self, client):
        for days in (30, 60, 120, 365):
            assert self._score(client, window_days=days)["supply_continuity"] <= 97


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
