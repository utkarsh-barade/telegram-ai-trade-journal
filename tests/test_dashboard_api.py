"""
Unit tests for Dashboard REST API endpoints and Authentication (api/auth.py & api/dashboard.py).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from bot.main import app
from services import auth_service

client = TestClient(app)


class TestAuthAPI:
    def test_login_success(self):
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["username"] == "admin"

    def test_login_failure(self):
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "wrongpassword"})
        assert resp.status_code == 401

    def test_protected_route_without_token(self):
        resp = client.get("/api/dashboard/overview")
        assert resp.status_code == 401

    def test_get_profile_with_token(self):
        login_resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        token = login_resp.json()["access_token"]

        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "admin"


class TestDashboardAPI:
    @pytest.fixture
    def auth_headers(self):
        login_resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        token = login_resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_create_and_get_trade(self, auth_headers):
        payload = {
            "stock": "INFY",
            "strike": 1800.0,
            "option_type": "CE",
            "direction": "BUY",
            "entry_price": 45.0,
            "stop_loss": 40.0,
            "capital": 100000.0,
            "notes": "Testing dashboard entry",
            "targets": [
                {"level": "TG1", "target_price": 50.0, "planned_qty_pct": 50.0, "status": "PENDING"},
                {"level": "FINAL", "target_price": 55.0, "planned_qty_pct": 50.0, "status": "PENDING"},
            ],
        }

        # Create
        resp = client.post("/api/dashboard/trade", json=payload, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        trade_id = data["id"]
        assert data["stock"] == "INFY"
        assert len(data["targets"]) == 2

        # Overview
        ov_resp = client.get("/api/dashboard/overview", headers=auth_headers)
        assert ov_resp.status_code == 200
        assert ov_resp.json()["total_trades"] >= 1

        # Trades list
        tr_resp = client.get("/api/dashboard/trades", headers=auth_headers)
        assert tr_resp.status_code == 200
        assert tr_resp.json()["total_count"] >= 1

        # Trade detail with audit history
        dt_resp = client.get(f"/api/dashboard/trade/{trade_id}", headers=auth_headers)
        assert dt_resp.status_code == 200
        assert "outcome_history" in dt_resp.json()

        # Update target leg to HIT
        update_payload = {
            "targets": [
                {"level": "TG1", "target_price": 50.0, "planned_qty_pct": 50.0, "status": "HIT", "exit_price": 50.0},
                {"level": "FINAL", "target_price": 55.0, "planned_qty_pct": 50.0, "status": "PENDING"},
            ],
            "outcome": "PARTIAL_EXIT",
        }
        up_resp = client.put(f"/api/dashboard/trade/{trade_id}", json=update_payload, headers=auth_headers)
        assert up_resp.status_code == 200
        assert up_resp.json()["outcome"] == "PARTIAL_EXIT"
        assert up_resp.json()["remaining_qty_pct"] == 50.0

        # Delete
        del_resp = client.delete(f"/api/dashboard/trade/{trade_id}", headers=auth_headers)
        assert del_resp.status_code == 200
