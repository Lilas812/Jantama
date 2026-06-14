# セットアップ（解析エンジンと雀魂取得を実際に動かす）

じゃん玉は「説明」を担当し、**推奨打牌の算出は Mortal**、**雀魂からの取得は変換ツール**に
委譲します。ここでは外部部品を実際に繋ぐ手順をまとめます。

まず外部部品なしで動く範囲から確認するのがおすすめです:

```bash
pip install -e '.[bot,dev]'
# 同梱フィクスチャで「根拠データ」を表示（API/エンジン不要）
jantama --review-json tests/fixtures/sample_review.json --no-explain
# 生の mjai ログを「牌効率エンジン」で解析（Mortal 不要）
jantama --log tests/fixtures/sample_game.mjai.jsonl --engine efficiency --no-explain
```

> **Mortal を用意しない場合**は `--engine efficiency`（または `.env` の
> `JANTAMA_ENGINE=efficiency`）で、Mortal 無しで生の mjai ログを解析できます。
> 牌効率のみの近似ですが、すぐ動かせます。以下 2 章は Mortal を使う場合のみ必要です。

---

## 1. Claude（説明の生成）

最小構成。これだけで `--review-json` から説明・総評が出せます。

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
jantama --review-json tests/fixtures/sample_review.json --actor 0
```

モデルや思考量は `.env`（`JANTAMA_CLAUDE_MODEL` / `JANTAMA_CLAUDE_EFFORT`）または
`--model` / `--effort` で変更できます。既定は `claude-opus-4-8` / `medium`。

---

## 2. 解析エンジン（Mortal + mjai-reviewer）

推奨打牌・期待値の算出には Mortal を mjai-reviewer 経由で使います。

- mjai-reviewer: https://github.com/Equim-chan/mjai-reviewer
- Mortal: https://github.com/Equim-chan/Mortal

### 手順の概要

1. **mjai-reviewer をビルド**（Rust が必要。本環境にも `cargo` あり）

   ```bash
   git clone https://github.com/Equim-chan/mjai-reviewer
   cd mjai-reviewer && cargo build --release
   # 生成物: target/release/mjai-reviewer
   ```

2. **Mortal 本体とモデル重み(.pth)を用意**
   Mortal のコードは公開されていますが、**学習済みモデル重みは再配布されていません**。
   公式リポジトリの案内に従って入手・学習してください。`mortal.pth` と設定ファイル
   (`config.toml` 等) を手元に置きます。

3. **環境変数を設定**（`.env`）

   ```ini
   MJAI_REVIEWER_PATH=/path/to/mjai-reviewer/target/release/mjai-reviewer
   MORTAL_MODEL_PATH=/path/to/mortal/config.toml
   MORTAL_DEVICE=cpu
   ```

4. **起動コマンドの確認・調整**
   mjai-reviewer のフラグはバージョンで変わります。まず手動で動作確認し、

   ```bash
   "$MJAI_REVIEWER_PATH" --help
   ```

   フラグが既定と違う場合は、コードを編集せず **`MJAI_REVIEWER_CMD`** で
   起動コマンドを上書きできます（`{in}`/`{out}`/`{actor}`/`{model}` を置換）:

   ```ini
   MJAI_REVIEWER_CMD=mjai-reviewer -e mortal -i {in} -a {actor} --json -o {out}
   ```

   実行に失敗すると、実際に走らせたコマンドと stderr がエラーに出るので調整の
   手がかりになります。`build_command()` を直接調整しても構いません。

5. **実行**

   ```bash
   jantama --url "https://tenhou.net/0/?log=....&tw=2"   # 天鳳 URL を直接
   jantama --log tenhou_log.json --actor 0              # 天鳳形式ファイル
   ```

### 入力フォーマット（重要）

mjai-reviewer の入力は **天鳳(tenhou.net/6)形式** です。`mortal` エンジンでは
`--url`(URL)・天鳳ログID・`--log`(天鳳形式ファイル) を渡してください。アダプタが
URL/ID/ファイルを判別して `-u`/`-t`/`-i` を使い分けます。出力 JSON には `mjai_log`
が含まれ、そこから手牌・ドラ・河・副露・押し引きを自動補完します。

> **mjai 形式のログ**は `efficiency` エンジン用です（`--engine efficiency`）。
> 形式が逆だと mjai-reviewer が「failed to parse tenhou.net/6 log」で失敗します。

---

## 3. 雀魂の牌譜取得

雀魂のログは認証＋独自形式のため、**天鳳形式に変換してから** `mortal` に渡します。
mjai-reviewer 公式の mjsoul ガイドでも、ブラウザでログを保存→天鳳形式ファイルを
渡す方法が推奨されています。

### 方法A: ブラウザでログを保存（推奨・確実）

1. ブラウザに Tampermonkey 等を入れ、「ログ保存」スクリプト/MOD を導入
   （mjai-reviewer の `mjsoul.adoc` 参照: `downloadlogs` スクリプト、または
   Majsoul+ の "Save logs" 機能）。
2. 雀魂で対局を開いてログを保存すると、**天鳳形式の JSON ファイル**が得られる。
3. そのファイルを渡すだけ:

   ```bash
   jantama --log saved_log.json --actor 2   # mortal(既定)。--actor は自分の席
   ```

### 方法B: tensoul で自動取得（不安定）

[tensoul](https://github.com/Equim-chan/tensoul) は雀魂→天鳳形式の自動変換ツール
ですが、雀魂側のログイン制限で失敗することがあります（公式 heroku は BAN 済み・
自前デプロイが必要）。使う場合は出力を**天鳳形式**にして設定:

```ini
TENSOUL_PATH=/path/to/tensoul
MAJSOUL_ACCESS_TOKEN=...
MAJSOUL_FETCH_CMD=tensoul {id} -o {out} --token {token}
```

> **別アカウント＋専用環境での実行を強く推奨**（公式ガイドの警告）。
> `efficiency` エンジンは mjai 形式入力なので、雀魂を解析するなら基本は `mortal`
> （天鳳形式）です。

---

## 4. Discord bot

```ini
DISCORD_BOT_TOKEN=...
```

```bash
python -m jantama.bot
```

- スラッシュコマンド `/kaisetsu url:<牌譜URL> [actor:0-3]`
- bot にメンションして牌譜URLを貼る / mjaiログ(.json/.jsonl)を添付

Discord Developer Portal で bot を作成し、`message_content` インテントを有効化、
`applications.commands` と `bot` スコープでサーバーに招待してください。

---

## トラブルシュート

| 症状 | 対処 |
|---|---|
| `mjai-reviewer が見つかりません` | `MJAI_REVIEWER_PATH` を実行ファイルの絶対パスに |
| `mjai-reviewer の実行に失敗` | `--help` で正しいフラグを確認し `build_command()` を調整 |
| 雀魂 `牌譜変換に失敗` | トークン期限切れ / ツールの引数違い。`build_command()` を確認 |
| 説明が出ない（API キー） | `ANTHROPIC_API_KEY` を設定。`--no-explain` でエンジン部分だけ切り分け |
| 全部入りで切り分けたい | `--review-json` で説明層のみ、`--no-explain` でエンジン層のみを個別に確認 |
