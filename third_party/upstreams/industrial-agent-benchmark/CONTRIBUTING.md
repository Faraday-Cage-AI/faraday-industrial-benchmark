# Contributing to Industrial Agent Benchmark

Industrial Agent Benchmark への貢献に関心を持っていただきありがとうございます。このドキュメントは、新しいベンチマーク問題の追加手順を中心に、コントリビューションの流れを説明します。

(English summary: this guide explains how to contribute, primarily how to add new benchmark tasks. Task content must be written in Japanese — Japanese is the canonical language of this benchmark. Tooling, docs, and CI contributions in English are welcome.)

## 開発環境のセットアップ

- Python 3.10 以上
- 依存関係のインストール:

```bash
pip install -r requirements-dev.txt
```

## 変更の種類

| 変更 | 主な対象 | 必須チェック |
|---|---|---|
| 問題の追加・修正 | `benchmark_data/**/*.yaml` | 下記「新しい問題の追加手順」 |
| スクリプト・評価パイプライン | `scripts/`, `eval/` | `pytest` + 既存挙動の互換性 |
| ドキュメント | `README*`, `docs/`, `dataset_card.md` | バージョン識別子の整合(`docs/versioning_policy.md`) |

## 新しい問題の追加手順

### 1. 配置先とIDを決める

問題は1問1ファイルで、レイヤーとカテゴリのディレクトリに配置します:

```text
benchmark_data/<layer_dir>/<category>/<ID>.yaml
```

- layer_dir: `knowledge`(IK)/ `reasoning`(IR)/ `agent`(IA)
- ID形式: `<レイヤー略号>-<カテゴリ略号>-<3桁連番>`(例: `IK-QUAL-006`, `IR-NCP-011`, `IA-WD-015`)
- レイヤー・カテゴリ・略号の正式な対応表は `scripts/validate_dataset.py` の `VALID_CATEGORIES` / `CATEGORY_PREFIX` と `docs/benchmark_spec.md` を参照してください。

### 2. YAML を書く

必須フィールド(詳細仕様は `docs/benchmark_spec.md`):

```yaml
id: IK-QUAL-006
layer: industrial_knowledge        # industrial_knowledge / industrial_reasoning / industrial_agent
category: quality                  # レイヤーごとの有効カテゴリから選択
domain: general_manufacturing      # automotive / electronics / medical_device / heavy_machinery / general_manufacturing
subdomain: inspection              # VALID_SUBDOMAINS から選択
difficulty: 3                      # 1..5 の整数
estimated_time_min: 30             # 正の整数
title: <一行タイトル>
scenario: |
  <現場の状況説明>
question: |
  <問い>
expected_skills: [skill_a, skill_b]
primary_skill: skill_a             # expected_skills に含まれること
secondary_skills: [skill_b]        # expected_skills の部分集合、primary と重複不可
reference_answer: |
  <公開参照解答>
evaluation_rubric:
  must_have:                       # 非空必須
    - <必須要素>
  nice_to_have:
    - <加点要素>
  critical_failures:               # 非空必須
    - <即減点となる危険な回答>
reasoning_trace_required: true
```

問題設計の原則:

- **タスク本文(title / scenario / question / reference_answer / rubric)は日本語で書く。** 日本語が本ベンチマークの canonical language です(`docs/japanese_canonical_policy_v2_2.md`)。機械可読なスキーマキー・enum値・技術略語(CAPA, FMEA 等)は英語のままで構いません。
- **generic answer で高得点にならない問題にする。** シナリオ固有の数値・制約・関係者を使わないと must_have を満たせないように設計してください。
- **critical_failures には「現場で実害が出る回答」を書く。** 例: 承認なしの自動実行、封じ込めをしない出荷継続。
- 数値制約を持つ問題は、v1.1 拡張フィールド(`numeric_checks`, `score_cap_rules`, `structured_output_requirements` 等)の追加を検討してください(任意)。

### 3. index を再生成し、検証する

```bash
python scripts/generate_dataset.py        # index.yaml / index.csv を再生成
python scripts/validate_dataset.py        # エラー0であること
```

### 4. JSONL をエクスポートし、検証する

```bash
python scripts/export_hf_dataset_v2.py                       # data/v2/test.jsonl を再生成
python scripts/validate_hf_dataset_v2.py data/v2/test.jsonl  # エラー0であること
```

`data/v2/test.jsonl` の差分も必ずコミットに含めてください。CI は「export 結果とコミット済み JSONL の一致」を検査します。

### 5. テストを実行する

```bash
python -m pytest tests/ -q
```

### 6. CHANGELOG に追記して PR を出す

- `CHANGELOG.md` の `[Unreleased]` セクションに変更を1行追記してください。
- PR テンプレートのチェックリストを埋めてください。

## コミットしてはいけないもの(Public Artifact Policy)

正典は [docs/public_artifact_policy_v1.md](docs/public_artifact_policy_v1.md) です。以下のリストはその要約です。文書化された正式 baseline 実験の公開物のみ、正典 §3 の限定例外(再現性メタデータの公開)に従います。非正式 run・開発 run・Fugu 系 run の生成物は従来どおり公開・コミットしません。

以下は PR に**絶対に含めないでください**:

- 生成されたモデル回答(raw model answers)
- `results/`, `results_v2/`, `datasets/results/` 配下の出力
- judge の入力・出力ファイル
- プロバイダ固有の評価結果、内部モデル名のマッピング
- APIキー、`.env`、トークン、認証情報
- 非公開レポート

## CI について

すべての PR で GitHub Actions(`.github/workflows/ci.yml`)が以下を実行します:

1. `validate_dataset.py`(YAML検証)
2. `export_hf_dataset_v2.py` + `git diff --exit-code data/v2/test.jsonl`(JSONL同期検査)
3. `validate_hf_dataset_v2.py`(JSONL検証)
4. `pytest tests/`

ローカルで上記がすべて通っていれば CI も通ります。

## 質問

不明点は [Question issue](../../issues/new?template=question.yml) でお気軽にどうぞ。
