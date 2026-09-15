# Industrial Agent Benchmark

Industrial Agent Benchmark は、製造業向け AI、Manufacturing AI Assistant、Industrial Agent を評価するための公開ベンチマークです。

日本語を canonical language とし、製造現場で重要になる知識、推論、エージェント動作を 3 層で評価します。英語版は今後、日本語 canonical dataset から派生する translated distribution として扱います。

English overview: [README_EN.md](README_EN.md)

## 現在のリリース

**v2.2.0: Japanese Canonical Normalization**

v2.2.0 では、v2.0.x で残っていた English-only tasks を日本語 canonical form へ移行しました。

- Total: 180 tasks
- Knowledge: 60
- Reasoning: 60
- Agent: 60
- English-only tasks: 45 -> 0
- Validation/export pipeline: preserved
- Primary dataset file: `data/v2/test.jsonl`

注意: リリースバージョン(v2.2.0)と、`data/v2/test.jsonl` の各レコードが持つ `version` フィールド(JSONL スキーマバージョン、現在 `2.0.0`)は別の識別子です。スキーマは v2.0.0 から変更されていないため `version: "2.0.0"` のままです。詳細は [docs/versioning_policy.md](docs/versioning_policy.md) を参照してください。

## Why Industrial Agent Benchmark?

製造業で AI エージェントを使う場合、一般的な会話能力だけでは不十分です。現場では、品質保留、出荷判定、CAPA、FMEA、工程変更、設備制約、要員制約、承認境界、監査証跡が実務判断に直結します。

Industrial Agent Benchmark は、次の観点を評価するために設計されています。

- 製造業の基本知識を正しく扱えるか
- 数値制約、能力、歩留まり、リスクを踏まえて推論できるか
- 人による承認が必要な行動を自律実行しないか
- 推奨、ドラフト、実行、リリース、出荷を区別できるか
- 監査可能な証拠、判断、エスカレーションを残せるか

## Dataset Overview

| Layer | Count | Focus |
|---|---:|---|
| Industrial Knowledge | 60 | 製造知識、手順、品質、保全、変更管理 |
| Industrial Reasoning | 60 | 根本原因分析、FMEA、CAPA、リスク判断、数値能力計画 |
| Industrial Agent | 60 | workflow design、tool selection、human-in-the-loop、承認境界、監査性 |
| Total | 180 |  |

Primary JSONL artifact:

```text
data/v2/test.jsonl
```

Dataset card:

```text
dataset_card.md
```

Hugging Face Dataset:

```text
https://huggingface.co/datasets/MSakae/industrial-agent-benchmark
```

## Quick Start

### Requirements

- Python 3.10+
- PyYAML

```bash
pip install pyyaml
```

### Validate benchmark YAML

```bash
python scripts/validate_dataset.py
```

Expected output:

```text
Checked: 180 problem files
Errors: 0
Warnings:0
```

### Export and validate HF-compatible JSONL

```bash
python scripts/export_hf_dataset_v2.py
python scripts/validate_hf_dataset_v2.py data/v2/test.jsonl
```

### Load locally

```bash
python examples/load_dataset_v2.py
```

## Evaluation Architecture

### 現状の実装ステータス

**現在実装されている評価は placeholder / experimental です。公式の Judge はまだ実装されていません。**

- 現行の判定器は `rule_based_token_overlap_v2`(token overlap によるルールベース採点)で、評価パイプラインのファイル形式・配管を検証するための placeholder です。ASCII 単語トークンに加え、日本語(ひらがな・カタカナ・漢字)は文字バイグラムでトークン化するため、日本語 canonical データでも配管検証が可能です。
- **このスコアをベンチマーク結果やモデル比較として使用しないでください。** 採点は表層的なトークン一致のみで、意味・根拠・rubric 準拠は評価していません。
- 公式スコア・リーダーボードは未提供です。

### 評価導線の使い分け

| 導線 | 対象 | 状態 | 用途 |
|---|---|---|---|
| `scripts/validate_dataset.py` / `scripts/export_hf_dataset_v2.py` / `scripts/validate_hf_dataset_v2.py` | 180問全体 | Stable | データ検証・JSONLエクスポート。まずここから |
| `eval/run_simple_eval.py` → `eval/run_judge_eval.py` → `eval/summarize_judge_eval.py` | 180問全体 | Placeholder | 自前で生成した回答ファイルを共通スキーマに整形し、placeholder scorer で配管検証する |
| `scripts/eval_v2_*` | `evaluation_set_v2.yaml` の30問サブセット | Experimental | LLM Judge を用いた評価実験。外部 API は opt-in(デフォルトは dummy/dry-run) |

新規利用者への推奨: まずデータ検証とロード(`examples/load_dataset_v2.py`)を行い、回答生成は自身の評価ハーネスで実施してください。本リポジトリの採点スクリプトは現時点では実験用です。

### Judge Roadmap(planned)

以下の Judge 構成は設計済み・**未実装**です。詳細は [docs/evaluation_architecture_v2.md](docs/evaluation_architecture_v2.md) を参照してください。

| Layer | Planned judge |
|---|---|
| Industrial Knowledge | Deterministic Judge(キーワード・数値・スキーマチェック) |
| Industrial Reasoning | Rubric Judge + numeric checks(LLM Judge 併用) |
| Industrial Agent | Executable Judge(tool trace・状態遷移・承認境界の実行検証) |

The repository includes validation, export, schema documentation, and local evaluation utilities. It does not include generated model answers, private judge outputs, provider-specific results, or leaderboard data.

## Public Artifact Policy

正典は [docs/public_artifact_policy_v1.md](docs/public_artifact_policy_v1.md) です。以下のリストはその要約です。文書化された正式 baseline 実験の公開物のみ、正典 §3 の限定例外(再現性メタデータの公開)に従います。非正式 run・開発 run・Fugu 系 run の生成物は従来どおり公開・コミットしません。

Do not commit:

- raw model answers
- `results/`
- `results_v2/`
- judge inputs or judge outputs
- provider-specific evaluation results
- private reports
- API keys, `.env`, tokens, credentials

## Contributing

問題の追加手順・検証フロー・PRチェックリストは [CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。すべての PR で CI(データ検証、JSONL同期検査、テスト)が実行されます。変更履歴は [CHANGELOG.md](CHANGELOG.md) にあります。

## Citation

引用には [CITATION.cff](CITATION.cff)(GitHub の "Cite this repository" 対応)を利用してください。

## License

Code: Apache License 2.0. See [LICENSE](LICENSE).

Dataset: see [LICENSE_DATASET.md](LICENSE_DATASET.md).
