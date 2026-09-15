# Summary / 概要

<!-- What does this PR change and why? / このPRは何をなぜ変更しますか -->

## Type of change / 変更種別

- [ ] New benchmark task(s) / 新規問題の追加
- [ ] Fix to existing task(s) / 既存問題の修正
- [ ] Scripts / evaluation pipeline / スクリプト・評価パイプライン
- [ ] Documentation / ドキュメント
- [ ] CI / tooling

## Checklist / チェックリスト

- [ ] `python scripts/validate_dataset.py` passes with 0 errors
- [ ] Task added/changed: `python scripts/generate_dataset.py` was run to regenerate the index / 問題を追加・変更した場合は index を再生成した
- [ ] `python scripts/export_hf_dataset_v2.py` was run and `data/v2/test.jsonl` is in sync / JSONL が同期している
- [ ] `python scripts/validate_hf_dataset_v2.py data/v2/test.jsonl` passes
- [ ] `python -m pytest tests/ -q` passes
- [ ] No generated model answers, judge outputs, provider-specific results, credentials, or private reports are included (Public Artifact Policy) / 生成回答・judge出力・認証情報等を含まない
- [ ] Task content is Japanese canonical (see CONTRIBUTING.md) / タスク本文は日本語 canonical
- [ ] `CHANGELOG.md` `[Unreleased]` updated / CHANGELOG の Unreleased に追記した
