from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from madewithml import serve


@pytest.fixture()
def client(monkeypatch):
    """Build a test app without external MLflow/model dependencies."""
    monkeypatch.setenv("DRIFT_MONITOR_ENABLED", "0")
    monkeypatch.setattr(serve, "Instrumentator", None)
    monkeypatch.setattr(serve.mlflow, "set_tracking_uri", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(serve.predict, "get_model_dir", lambda run_id: Path("."))
    monkeypatch.setattr(serve.predict.TorchPredictor, "from_model_dir", classmethod(lambda cls, model_dir: object()))

    def fake_predict_proba(df, predictor):
        text = f"{df.iloc[0]['title']} {df.iloc[0]['description']}".lower()
        if "low-confidence" in text:
            return [
                {
                    "prediction": "natural-language-processing",
                    "probabilities": {
                        "computer-vision": 0.20,
                        "mlops": 0.20,
                        "natural-language-processing": 0.40,
                        "other": 0.20,
                    },
                }
            ]
        return [
            {
                "prediction": "natural-language-processing",
                "probabilities": {
                    "computer-vision": 0.02,
                    "mlops": 0.01,
                    "natural-language-processing": 0.95,
                    "other": 0.02,
                },
            }
        ]

    monkeypatch.setattr(serve.predict, "predict_proba", fake_predict_proba)

    app = serve.create_app(run_id="ci-test-run", threshold=0.9)
    return TestClient(app)


def test_health_endpoint_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status-code"] == 200


def test_predict_accepts_json_body(client):
    payload = {
        "title": "NLP project",
        "description": "Transformer text classification",
    }
    response = client.post("/predict/", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "results" in body
    assert body["results"][0]["prediction"] == "natural-language-processing"


def test_predict_threshold_routes_to_other_for_low_confidence(client):
    payload = {
        "title": "low-confidence sample",
        "description": "force threshold fallback",
    }
    response = client.post("/predict/", json=payload)
    assert response.status_code == 200
    assert response.json()["results"][0]["prediction"] == "other"


def test_predict_invalid_json_returns_400(client):
    response = client.post(
        "/predict/",
        content="{'title':'bad-json'}",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert "Invalid JSON body" in response.json()["detail"]

