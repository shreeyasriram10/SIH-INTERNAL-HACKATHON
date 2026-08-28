import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from main import app
from ml.train import train_model

client = TestClient(app)

@pytest.fixture(scope="session", autouse=True)
def ensure_model():
    model_path = os.path.join(os.path.dirname(__file__), "..", "ml", "model.pkl")
    if not os.path.exists(model_path):
        train_model()

# ---------- 1. PAGE ROUTING & AUTH TESTS ----------
class TestPageRoutes:
    def test_root_serves_signin_gateway(self):
        """GET / must return the Ministry of Steel Sign In gateway."""
        r = client.get("/")
        assert r.status_code == 200
        assert "LOHA DRISHTI" in r.text
        assert "Ministry of Steel" in r.text
        assert "Secure Authentication" in r.text

    def test_app_serves_dashboard(self):
        """GET /app must return the main LOHA-DRISHTI dashboard."""
        r = client.get("/app")
        assert r.status_code == 200
        assert "LOHA DRISHTI" in r.text
        assert "Command Center" in r.text
        assert "Watch Demo" in r.text

    def test_login_page_serves(self):
        """GET /login must return the dedicated Sign In page."""
        r = client.get("/login")
        assert r.status_code == 200
        assert "LOHA DRISHTI" in r.text
        assert "Secure Authentication" in r.text

    def test_ml_training_page_serves(self):
        """GET /ml-training must return the ML Model & Training page."""
        r = client.get("/ml-training")
        assert r.status_code == 200
        assert "ML Model" in r.text
        assert "RETRAIN" in r.text

    def test_system_verification_page_serves(self):
        """GET /verification must return the System Verification tester page."""
        r = client.get("/verification")
        assert r.status_code == 200
        assert "System Verification" in r.text
        assert "TEST SUITE" in r.text

    def test_api_docs_accessible(self):
        """GET /docs must return OpenAPI Swagger documentation."""
        r = client.get("/docs")
        assert r.status_code == 200

# ---------- 2. AUTHENTICATION API TESTS ----------
class TestAuthAPI:
    def test_login_valid(self):
        """Valid admin@sail.gov.in / admin123 credentials return JWT token."""
        r = client.post(
            "/api/auth/login",
            data={"username": "admin@sail.gov.in", "password": "admin123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "Chief Logistics Officer"

    def test_login_invalid(self):
        """Invalid credentials return 401 Unauthorized."""
        r = client.post(
            "/api/auth/login",
            data={"username": "admin@sail.gov.in", "password": "wrongpassword999"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert r.status_code == 401

# ---------- 3. ML PIPELINE & METRICS TESTS ----------
class TestMLPipeline:
    def test_ml_info(self):
        """GET /api/ml/info returns model metrics (R2, MAE, RMSE)."""
        r = client.get("/api/ml/info")
        assert r.status_code == 200
        data = r.json()
        assert "algorithm" in data
        assert "r2_score" in data
        assert "mae_usd" in data
        assert data["r2_score"] > 0.90

    def test_ml_prediction(self):
        """POST /api/ml/predict returns valid rate and confidence interval."""
        r = client.post("/api/ml/predict", json={
            "origin": "Australia",
            "distance_nm": 4500,
            "month": 6,
            "bunker_price": 640.0,
            "pressure_index": 45.0
        })
        assert r.status_code == 200
        data = r.json()
        assert "predicted_rate_usd" in data
        assert "confidence_interval" in data
        assert 10.0 < data["predicted_rate_usd"] < 70.0

# ---------- 4. DATABASE & SYSTEM TESTER ----------
class TestDatabaseAndSystem:
    def test_system_status(self):
        """GET /api/system/status returns connected database & operational status."""
        r = client.get("/api/system/status")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "OPERATIONAL"
        assert data["database"]["status"] == "Connected"

    def test_live_system_tests(self):
        """GET /api/system/run-tests executes live test battery with 100% pass."""
        r = client.get("/api/system/run-tests")
        assert r.status_code == 200
        data = r.json()
        assert data["overall_status"] == "ALL_TESTS_PASSING"
        assert data["failed"] == 0
