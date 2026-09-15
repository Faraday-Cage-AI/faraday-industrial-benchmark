"""Regression tests for the placeholder scorer in eval/run_judge_eval.py.

The scorer is a pipeline-validation placeholder, not a semantic judge; these
tests pin its tokenization behavior (ASCII words + Japanese character
bigrams) and score boundaries.
"""
from __future__ import annotations

import run_judge_eval as rj


def test_score_method_is_versioned_v2():
    assert rj.SCORE_METHOD == "rule_based_token_overlap_v2"


def test_ascii_tokenization_unchanged_from_v1():
    # ASCII behavior: lowercased word tokens of length >= 3.
    assert rj.tokenize("Keep the lot ON hold_123 x ab") == {"keep", "the", "lot", "hold_123"}


def test_japanese_bigram_tokenization():
    tokens = rj.tokenize("出荷停止")
    assert tokens == {"出荷", "荷停", "停止"}


def test_japanese_single_char_run():
    assert "図" in rj.tokenize("図8を参照")


def test_mixed_language_tokenization():
    tokens = rj.tokenize("CAPA を発行し 8D レポートを作成")
    assert "capa" in tokens
    assert "レポ" in tokens
    assert "作成" in tokens


def test_empty_prediction_scores_zero():
    score, metadata = rj.score_prediction("", "参照解答", "rubric")
    assert score == 0
    assert metadata["reason"] == "missing_prediction"


def test_identical_japanese_prediction_scores_five():
    reference = "同一梱包条件・時間帯を中心とした安全側の暫定封じ込め範囲設定を行う。"
    score, metadata = rj.score_prediction(reference, reference, "")
    assert score == 5
    assert metadata["overlap_ratio"] == 1.0


def test_unrelated_japanese_prediction_scores_low():
    score, metadata = rj.score_prediction(
        "今日は良い天気なので公園を散歩します。",
        "設備停止時のロット保留と出荷判定基準を確認する。",
        "",
    )
    assert score <= 1
    assert metadata["reason"] == "token_overlap"


def test_japanese_text_produces_tokens_not_insufficient():
    # v1 regression: ASCII-only tokenization returned empty token sets for
    # Japanese text and every answer collapsed to score 1.
    score, metadata = rj.score_prediction("品質保証部門へ報告する", "品質保証部門へ報告する", "")
    assert metadata["reason"] == "token_overlap"
    assert metadata["prediction_token_count"] > 0
