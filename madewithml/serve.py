import argparse
import json
import os
from pathlib import Path
from http import HTTPStatus
from typing import Dict

import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException
from starlette.requests import Request

from madewithml import evaluate, predict
from madewithml.config import MLFLOW_TRACKING_URI, ROOT_DIR, logger, mlflow
from madewithml.drift_monitor import DriftMonitor

try:
    from prometheus_fastapi_instrumentator import Instrumentator
except ImportError:  # pragma: no cover - optional local dependency
    Instrumentator = None

app = FastAPI(
    title="Made With ML",
    description="Classify machine learning projects.",
    version="0.1",
)


async def get_prediction_input(request: Request, title: str = "", description: str = "") -> Dict:
    """Get prediction inputs from a JSON body or query parameters."""
    data = {}
    body = await request.body()
    if body:
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=400,
                detail="Invalid JSON body. Use a JSON object with double-quoted keys and values.",
            ) from exc
        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail="Invalid JSON body. Expected an object.")
    return {
        "title": data.get("title", title) or "",
        "description": data.get("description", description) or "",
    }


def make_json_safe(results):
    """Convert numpy values in prediction results to JSON-safe Python types."""
    safe_results = []
    for result in results:
        safe_results.append(
            {
                "prediction": result["prediction"],
                "probabilities": {label: float(prob) for label, prob in result["probabilities"].items()},
            }
        )
    return safe_results


def _is_enabled(value: str, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _get_int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
        if value < 1:
            raise ValueError
        return value
    except ValueError:
        logger.warning("Invalid %s=%s. Falling back to %s.", name, raw, default)
        return default


def _init_drift_monitor() -> DriftMonitor | None:
    if not _is_enabled(os.environ.get("DRIFT_MONITOR_ENABLED"), default=True):
        return None

    baseline_path = Path(
        os.environ.get("DRIFT_BASELINE_DATASET", str(Path(ROOT_DIR, "datasets", "dataset.csv")))
    )
    window_size = _get_int_env("DRIFT_WINDOW_SIZE", 500)
    vocab_top_k = _get_int_env("DRIFT_VOCAB_TOP_K", 200)

    if not baseline_path.exists():
        logger.warning("Drift monitoring disabled: baseline dataset not found at %s", baseline_path)
        return None

    monitor = DriftMonitor.from_dataset_csv(
        dataset_loc=str(baseline_path),
        window_size=window_size,
        vocab_top_k=vocab_top_k,
        enable_prometheus_metrics=True,
    )
    logger.info(
        "Drift monitoring enabled with baseline=%s, window_size=%s, vocab_top_k=%s",
        baseline_path,
        window_size,
        vocab_top_k,
    )
    return monitor


def create_app(run_id: str, threshold: float = 0.9) -> FastAPI:
    """Create a local FastAPI app."""
    local_app = FastAPI(
        title="Made With ML",
        description="Classify machine learning projects.",
        version="0.1",
    )
    if Instrumentator:
        Instrumentator().instrument(local_app).expose(local_app)
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    predictor = predict.TorchPredictor.from_model_dir(predict.get_model_dir(run_id=run_id))
    drift_monitor = _init_drift_monitor()

    @local_app.get("/")
    def _index() -> Dict:
        return {
            "message": HTTPStatus.OK.phrase,
            "status-code": HTTPStatus.OK,
            "data": {},
        }

    @local_app.get("/run_id/")
    def _run_id() -> Dict:
        return {"run_id": run_id}

    @local_app.post("/evaluate/")
    async def _evaluate(request: Request) -> Dict:
        data = await request.json()
        results = evaluate.evaluate(run_id=run_id, dataset_loc=data.get("dataset"))
        return {"results": results}

    @local_app.post("/predict/")
    async def _predict(request: Request, title: str = "", description: str = ""):
        data = await get_prediction_input(request=request, title=title, description=description)
        if drift_monitor is not None:
            try:
                drift_monitor.update(title=data["title"], description=data["description"])
            except Exception as exc:  # pragma: no cover - monitoring must not block predictions
                logger.warning("Drift metric update failed: %s", exc)
        sample_df = pd.DataFrame([{"title": data["title"], "description": data["description"], "tag": "other"}])
        results = predict.predict_proba(df=sample_df, predictor=predictor)

        for i, result in enumerate(results):
            pred = result["prediction"]
            prob = result["probabilities"]
            if prob[pred] < threshold:
                results[i]["prediction"] = "other"

        return {"results": make_json_safe(results)}

    return local_app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_id", help="run ID to use for serving.")
    parser.add_argument("--threshold", type=float, default=0.9, help="threshold for `other` class.")
    parser.add_argument("--server", choices=["uvicorn"], default="uvicorn", help="server backend to use.")
    parser.add_argument("--host", default="127.0.0.1", help="host to bind.")
    parser.add_argument("--port", type=int, default=8000, help="port to bind.")
    args = parser.parse_args()
    uvicorn.run(create_app(run_id=args.run_id, threshold=args.threshold), host=args.host, port=args.port)
