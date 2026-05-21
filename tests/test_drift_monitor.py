import pandas as pd

from madewithml.drift_monitor import (
    DriftMonitor,
    compute_kl_divergence,
    compute_psi,
    detect_language_bucket,
)


def test_compute_kl_divergence_zero_for_equal_distributions():
    value = compute_kl_divergence([0.5, 0.5], [0.5, 0.5])
    assert abs(value) < 1e-9


def test_compute_psi_detects_shift():
    stable = compute_psi([0.5, 0.5], [0.5, 0.5])
    shifted = compute_psi([0.9, 0.1], [0.2, 0.8])
    assert shifted > stable


def test_detect_language_bucket_basic_cases():
    assert detect_language_bucket("This project uses transformers and data.") == "en"
    assert detect_language_bucket("Ce projet est base sur des modeles.") == "fr"
    assert detect_language_bucket("\u0645\u0631\u062d\u0628\u0627 \u0647\u0630\u0627 \u0645\u0634\u0631\u0648\u0639 \u062a\u0639\u0644\u0645 \u0627\u0644\u0627\u0644\u0629") == "ar"


def test_drift_monitor_snapshot_outputs_expected_metrics():
    baseline_df = pd.DataFrame(
        [
            {"title": "Vision project", "description": "Image classification with cnn"},
            {"title": "NLP project", "description": "Transformer for text classification"},
            {"title": "Projet francais", "description": "Classification de texte avec modele"},
        ]
    )
    monitor = DriftMonitor(
        baseline_df=baseline_df,
        window_size=100,
        vocab_top_k=20,
        enable_prometheus_metrics=False,
    )
    snapshot = monitor.update(
        title="Analyse de donnees",
        description="Projet francais avec quelques termes inconnus xyzabc",
    )

    expected_keys = {
        "window_samples",
        "text_chars_psi",
        "text_tokens_psi",
        "language_kl",
        "vocab_kl",
        "oov_rate",
    }
    assert expected_keys == set(snapshot.keys())
    assert snapshot["window_samples"] == 1.0
    assert 0.0 <= snapshot["oov_rate"] <= 1.0
