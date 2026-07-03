import pytest
from fastapi.testclient import TestClient
import sys
import os
from unittest.mock import patch

# Mock some dependencies before importing app
with patch('scripts.bootstrap.perform_cold_start_if_needed'):
    import app.main

client = TestClient(app.main.app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@patch('app.main.state')
@patch('app.main.secrets.compare_digest', return_value=True)
def test_push_api_valid_key(mock_compare, mock_state):
    mock_state.get.side_effect = lambda k, d=None: "valid_key" if k == "secret_key" else d
    
    response = client.get("/api/push/valid_key")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["msg"] == "heartbeat_received"

@patch('app.main.state')
@patch('app.main.secrets.compare_digest', return_value=False)
def test_push_api_invalid_key(mock_compare, mock_state):
    mock_state.get.side_effect = lambda k, d=None: "actual_key" if k == "secret_key" else d
    
    response = client.get("/api/push/invalid_key")
    assert response.status_code == 403
    assert response.json()["status"] == "error"
    assert response.json()["msg"] == "invalid_key"

@patch('app.main.api_status')
def test_api_status_endpoint(mock_api_status):
    mock_api_status.return_value = {"status": "up", "last_seen": 12345}
    response = client.get("/api/status")
    assert response.status_code == 200

@patch('app.main.get_power_events_data')
def test_root_endpoint(mock_events):
    mock_events.return_value = [{"event": "up", "timestamp": 12345}]
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "power_safety_active_sse_connections" in response.text

import datetime

def test_get_wind_label_localization():
    assert app.main.get_wind_label(0, lang='ua') == "Пн"
    assert app.main.get_wind_label(0, lang='en') == "N"
    assert app.main.get_wind_label(45, lang='ua') == "ПнСх"
    assert app.main.get_wind_label(45, lang='en') == "NE"

def test_render_day_schedule_html_localization():
    slots = [True] * 48
    date_obj = datetime.date(2026, 6, 5)
    
    html_ua = app.main.render_day_schedule_html(slots, date_obj, lang='ua')
    html_en = app.main.render_day_schedule_html(slots, date_obj, lang='en')
    
    assert "Червня" in html_ua
    assert "June" in html_en
    assert "Power ON" in html_en
    assert "Увімкнення" in html_ua
