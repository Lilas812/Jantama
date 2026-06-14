# じゃん玉 (Jantama Explainer)

**雀魂(じゃんたま)の牌譜を解析し、「なぜその打牌が良いのか」を日本語で説明するツール。**

牌譜を解析するツール（NAGA / Mortal / 天鳳系）は「推奨打牌」と「一致率・悪手率・期待値」といった**数字とおすすめ牌**を出してくれます。一方で、**「なぜそうした方が良いのか」を人間のコーチのように言葉で説明**してくれるものは、ほとんどありません。じゃん玉はそこを埋めます。

---

## 仕組み（なぜ嘘をつかないか）

牌譜をそのまま LLM に投げると、麻雀の事実（牌の枚数・期待値など）を平気で捏造します。そこで **3 段構成** にして、確定した数値だけを根拠に説明させます。

```
雀魂の牌譜URL/ログ
   │  ① 取得・変換（mjai 形式へ）
   ▼
 mjai イベント列
   │  ② Mortal で解析（推奨打牌・期待値）   ← review/
   ▼
 評価付きの DecisionPoint
   │  ③ 向聴・受け入れ・ドラを自前計算       ← metrics/
   ▼
 確定した数値（根拠）
   │  ④ Claude が「なぜ」を日本語化          ← explain/
   ▼
 自然言語の説明（Discord / CLI）
```

ステップ②③で数値を確定させ、ステップ④の Claude はその**意味づけ**だけに専念します。これにより、もっともらしい嘘ではなく、根拠のある説明になります。

---

## プロジェクト構成

```
src/jantama/
  config.py            設定（環境変数 / .env から）
  models.py            DecisionPoint / Metrics / Explanation
  tiles.py             牌の表記・変換（mjai ↔ 34配列 ↔ 日本語）
  metrics/shanten.py   向聴数・受け入れ（ukeire）の計算   ← 説明の「根拠」
  review/              解析エンジン層（Mortal / mjai-reviewer アダプタ）
  sources/             入力源（雀魂URL・ローカル mjai ログ）
  explain/             Claude による説明生成（プロンプト + 呼び出し）
  pipeline.py          ①〜④のオーケストレーション
  cli.py               コマンドライン
  bot/discord_bot.py   Discord bot
tests/                 ユニットテスト（pytest）
```

---

## セットアップ

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e '.[bot,dev]'      # bot=Discord, dev=pytest
cp .env.example .env             # 各種キーを記入
```

`.env` の主な項目（詳細は `.env.example`）:

| 変数 | 用途 |
|---|---|
| `ANTHROPIC_API_KEY` | 説明文の生成（必須） |
| `JANTAMA_CLAUDE_MODEL` | 既定 `claude-opus-4-8` |
| `MJAI_REVIEWER_PATH` / `MORTAL_MODEL_PATH` | 解析エンジン（後述） |
| `TENSOUL_PATH` / `MAJSOUL_ACCESS_TOKEN` | 雀魂 URL からの取得（後述） |
| `DISCORD_BOT_TOKEN` | Discord bot |

---

## 使い方（CLI）

```bash
# ① 計算した根拠だけ表示（Claude 不要・オフライン確認用）
jantama --review-json tests/fixtures/sample_review.json --no-explain

# ② 既存の mjai-reviewer 出力から「説明」だけ生成（Mortal 不要・要 API キー）
jantama --review-json review.json --actor 0

# ③ 雀魂の牌譜URL（要 変換ツール + Mortal + API キー）
jantama --url "https://game.mahjongsoul.com/?paipu=..." --actor 0

# ④ ローカルの mjai ログ（要 Mortal + API キー）
jantama --log game.mjai.json --actor 0
```

`--no-explain` は API もエンジンも使わず、向聴・受け入れ・ドラ・期待値といった
「Claude に渡す根拠」をそのまま表示します。同梱フィクスチャで今すぐ動作確認できます。

## 使い方（Discord bot）

```bash
python -m jantama.bot
```

- スラッシュコマンド `/kaisetsu url:<牌譜URL> [actor:0-3]`
- もしくは bot にメンションして牌譜URLを貼る / mjaiログ(.json/.jsonl)を添付

---

## 解析エンジン（Mortal）について

精度の高い推奨打牌・期待値は、オープンソースの **Mortal** を
**mjai-reviewer** 経由で利用します。

- mjai-reviewer: https://github.com/Equim-chan/mjai-reviewer
- Mortal: https://github.com/Equim-chan/Mortal

Mortal の**学習済みモデル重み(.pth)は各自で用意**する必要があります（再配布されていません）。
入手後、`MJAI_REVIEWER_PATH` と `MORTAL_MODEL_PATH` を設定してください。
`review/mortal.py` の `build_command()` が起動コマンドの調整ポイントです。

## 雀魂の牌譜取得について

雀魂のログは protobuf + 認証が必要なため、取得・変換は外部ツール
（例: [tensoul](https://github.com/Equim-chan/tensoul)）に委譲します。
`TENSOUL_PATH` と `MAJSOUL_ACCESS_TOKEN` を設定すると URL から取得できます。
未設定でも、変換済みの mjai ログを渡せば解析できます（`--log` / bot への添付）。

---

## テスト

```bash
pytest -q
```

向聴・受け入れの計算、牌譜パーサ、説明プロンプトの組み立て、パイプライン
（Claude はフェイククライアントで代替）を検証します。ネットワーク不要。

---

## 実装状況

| 機能 | 状態 |
|---|---|
| 牌効率の計算（向聴・受け入れ・ドラ） | ✅ 実装・テスト済み |
| 副露(鳴き)時の牌効率計算 | ✅ 実装・テスト済み（七対子/国士を自動除外） |
| mjai-reviewer / Mortal 出力のパース | ✅ 実装・テスト済み |
| Claude による説明生成 | ✅ 実装・テスト済み（要 API キー） |
| CLI / Discord bot | ✅ 実装済み |
| Mortal 本体の実行 | ⚙️ アダプタ実装済み（モデル重みは要用意） |
| 雀魂 URL からの取得 | ⚙️ アダプタ実装済み（変換ツール+認証は要設定） |
| 副露牌のドラ集計 | 🔜 今後（現状は手牌中のみ。EV はエンジンが考慮） |
| 1 局通しのサマリ生成 | 🔜 今後 |
