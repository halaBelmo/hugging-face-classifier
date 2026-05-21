from __future__ import annotations

import re
from collections import Counter, deque
from dataclasses import dataclass
from typing import Deque, Dict, Iterable, List, Sequence

import numpy as np
import pandas as pd

from madewithml.data import clean_text

try:
    from prometheus_client import Gauge, REGISTRY
except ImportError:  # pragma: no cover - optional local dependency
    Gauge = None
    REGISTRY = None


EPSILON = 1e-8
CHAR_BINS = np.array([0, 20, 40, 80, 160, 320, 640, 1280, np.inf], dtype=float)
TOKEN_BINS = np.array([0, 5, 10, 20, 40, 80, 160, 320, np.inf], dtype=float)
LANGUAGE_BUCKETS = ("en", "fr", "ar", "other")
FRENCH_HINTS = {
    "le",
    "la",
    "les",
    "des",
    "du",
    "de",
    "pour",
    "avec",
    "dans",
    "une",
    "un",
    "est",
}
ENGLISH_HINTS = {
    "the",
    "for",
    "with",
    "this",
    "that",
    "using",
    "project",
    "model",
    "data",
    "and",
}


def _to_probabilities(values: Iterable[float], epsilon: float = EPSILON) -> np.ndarray:
    probs = np.asarray(list(values), dtype=float)
    probs = np.clip(probs, epsilon, None)
    probs /= probs.sum()
    return probs


def compute_kl_divergence(current: Iterable[float], baseline: Iterable[float], epsilon: float = EPSILON) -> float:
    """KL(current || baseline) with numerical stability."""
    cur = _to_probabilities(current, epsilon=epsilon)
    base = _to_probabilities(baseline, epsilon=epsilon)
    return float(np.sum(cur * np.log(cur / base)))


def compute_psi(baseline: Iterable[float], current: Iterable[float], epsilon: float = EPSILON) -> float:
    """Population Stability Index between baseline and current distributions."""
    base = _to_probabilities(baseline, epsilon=epsilon)
    cur = _to_probabilities(current, epsilon=epsilon)
    return float(np.sum((cur - base) * np.log(cur / base)))


def histogram_probabilities(values: np.ndarray, bins: np.ndarray) -> np.ndarray:
    hist, _ = np.histogram(values, bins=bins)
    if hist.sum() == 0:
        hist = np.ones(len(bins) - 1, dtype=float)
    return _to_probabilities(hist)


def detect_language_bucket(text: str) -> str:
    """Lightweight language bucket detection without external dependencies."""
    if not text:
        return "other"
    if re.search(r"[\u0600-\u06FF]", text):
        return "ar"

    lowered = text.lower()
    tokens = re.findall(r"[a-zA-Z\u00C0-\u00FF]+", lowered)
    if not tokens:
        return "other"

    fr_score = sum(token in FRENCH_HINTS for token in tokens)
    en_score = sum(token in ENGLISH_HINTS for token in tokens)
    has_french_accent = bool(
        re.search(r"[\u00E9\u00E8\u00EA\u00EB\u00E0\u00E2\u00EE\u00EF\u00F4\u00F6\u00F9\u00FB\u00FC\u00E7\u0153]", lowered)
    )
    if has_french_accent or fr_score > en_score:
        return "fr"
    if en_score >= fr_score:
        return "en"
    return "other"


@dataclass
class DriftRecord:
    char_len: int
    token_len: int
    lang: str
    tokens: List[str]


def _get_or_create_gauge(name: str, description: str):
    if Gauge is None or REGISTRY is None:
        return None
    existing = REGISTRY._names_to_collectors.get(name)  # pragma: no cover - registry internals
    if existing is not None:
        return existing
    return Gauge(name, description)


class DriftMonitor:
    """Compute online drift metrics against a train baseline."""

    def __init__(
        self,
        baseline_df: pd.DataFrame,
        window_size: int = 500,
        vocab_top_k: int = 200,
        enable_prometheus_metrics: bool = True,
    ):
        if baseline_df.empty:
            raise ValueError("baseline_df must contain at least one row.")

        self.window_size = int(max(window_size, 1))
        self.vocab_top_k = int(max(vocab_top_k, 1))
        self.records: Deque[DriftRecord] = deque(maxlen=self.window_size)
        self.enable_prometheus_metrics = enable_prometheus_metrics and Gauge is not None

        baseline_records = [self._build_record(row.get("title", ""), row.get("description", "")) for _, row in baseline_df.iterrows()]
        self._fit_baseline(baseline_records)
        self.metrics = self._init_metrics()

    @classmethod
    def from_dataset_csv(
        cls,
        dataset_loc: str,
        window_size: int = 500,
        vocab_top_k: int = 200,
        enable_prometheus_metrics: bool = True,
    ) -> "DriftMonitor":
        baseline_df = pd.read_csv(dataset_loc)
        return cls(
            baseline_df=baseline_df,
            window_size=window_size,
            vocab_top_k=vocab_top_k,
            enable_prometheus_metrics=enable_prometheus_metrics,
        )

    def _init_metrics(self) -> Dict[str, object]:
        if not self.enable_prometheus_metrics:
            return {}
        return {
            "window_samples": _get_or_create_gauge(
                "madewithml_drift_window_samples",
                "Number of samples used in the rolling drift window.",
            ),
            "text_chars_psi": _get_or_create_gauge(
                "madewithml_drift_text_length_chars_psi",
                "PSI between baseline and production text length in characters.",
            ),
            "text_tokens_psi": _get_or_create_gauge(
                "madewithml_drift_text_length_tokens_psi",
                "PSI between baseline and production text length in tokens.",
            ),
            "language_kl": _get_or_create_gauge(
                "madewithml_drift_language_kl",
                "KL divergence between baseline and production language distribution.",
            ),
            "vocab_kl": _get_or_create_gauge(
                "madewithml_drift_vocab_kl",
                "KL divergence between baseline and production top-token distribution.",
            ),
            "oov_rate": _get_or_create_gauge(
                "madewithml_drift_oov_rate",
                "Out-of-vocabulary token rate using baseline train vocabulary.",
            ),
        }

    def _build_record(self, title: str, description: str) -> DriftRecord:
        raw_text = f"{title or ''} {description or ''}".strip()
        cleaned_text = clean_text(raw_text)
        tokens = cleaned_text.split() if cleaned_text else []
        lang = detect_language_bucket(raw_text)
        return DriftRecord(
            char_len=len(cleaned_text),
            token_len=len(tokens),
            lang=lang if lang in LANGUAGE_BUCKETS else "other",
            tokens=tokens,
        )

    def _fit_baseline(self, baseline_records: Sequence[DriftRecord]):
        char_lens = np.array([record.char_len for record in baseline_records], dtype=float)
        token_lens = np.array([record.token_len for record in baseline_records], dtype=float)
        self.baseline_char_probs = histogram_probabilities(char_lens, CHAR_BINS)
        self.baseline_token_probs = histogram_probabilities(token_lens, TOKEN_BINS)

        lang_counts = Counter(record.lang for record in baseline_records)
        self.baseline_lang_probs = _to_probabilities([lang_counts.get(bucket, 0) for bucket in LANGUAGE_BUCKETS])

        vocab_counter = Counter()
        for record in baseline_records:
            vocab_counter.update(record.tokens)
        self.baseline_vocabulary = set(vocab_counter.keys())
        self.top_tokens = [token for token, _ in vocab_counter.most_common(self.vocab_top_k)]
        self.top_token_to_idx = {token: i for i, token in enumerate(self.top_tokens)}

        baseline_vocab_counts = np.zeros(len(self.top_tokens) + 1, dtype=float)  # +1 for other bucket
        for token, count in vocab_counter.items():
            idx = self.top_token_to_idx.get(token)
            if idx is None:
                baseline_vocab_counts[-1] += float(count)
            else:
                baseline_vocab_counts[idx] += float(count)
        if baseline_vocab_counts.sum() == 0:
            baseline_vocab_counts[:] = 1.0
        self.baseline_vocab_probs = _to_probabilities(baseline_vocab_counts)

    def update(self, title: str, description: str) -> Dict[str, float]:
        self.records.append(self._build_record(title=title, description=description))
        snapshot = self.snapshot()
        self._publish(snapshot)
        return snapshot

    def snapshot(self) -> Dict[str, float]:
        if not self.records:
            return {
                "window_samples": 0.0,
                "text_chars_psi": 0.0,
                "text_tokens_psi": 0.0,
                "language_kl": 0.0,
                "vocab_kl": 0.0,
                "oov_rate": 0.0,
            }

        char_lens = np.array([record.char_len for record in self.records], dtype=float)
        token_lens = np.array([record.token_len for record in self.records], dtype=float)
        current_char_probs = histogram_probabilities(char_lens, CHAR_BINS)
        current_token_probs = histogram_probabilities(token_lens, TOKEN_BINS)

        lang_counts = Counter(record.lang for record in self.records)
        current_lang_probs = _to_probabilities([lang_counts.get(bucket, 0) for bucket in LANGUAGE_BUCKETS])

        vocab_counts = np.zeros(len(self.top_tokens) + 1, dtype=float)
        total_tokens = 0
        total_oov = 0
        for record in self.records:
            for token in record.tokens:
                total_tokens += 1
                if token in self.baseline_vocabulary:
                    idx = self.top_token_to_idx.get(token)
                    if idx is None:
                        vocab_counts[-1] += 1.0
                    else:
                        vocab_counts[idx] += 1.0
                else:
                    total_oov += 1
                    vocab_counts[-1] += 1.0

        if vocab_counts.sum() == 0:
            vocab_counts[:] = 1.0
        current_vocab_probs = _to_probabilities(vocab_counts)
        oov_rate = (total_oov / total_tokens) if total_tokens else 0.0

        return {
            "window_samples": float(len(self.records)),
            "text_chars_psi": compute_psi(self.baseline_char_probs, current_char_probs),
            "text_tokens_psi": compute_psi(self.baseline_token_probs, current_token_probs),
            "language_kl": compute_kl_divergence(current_lang_probs, self.baseline_lang_probs),
            "vocab_kl": compute_kl_divergence(current_vocab_probs, self.baseline_vocab_probs),
            "oov_rate": float(oov_rate),
        }

    def _publish(self, snapshot: Dict[str, float]):
        if not self.enable_prometheus_metrics:
            return
        for key, gauge in self.metrics.items():
            if gauge is not None:
                gauge.set(float(snapshot[key]))
