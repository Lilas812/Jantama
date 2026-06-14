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

雀魂のログは protobuf + 認証が必要なため、取得・変換は外部ツールに委譲します。
代表例: [tensoul](https://github.com/Equim-chan/tensoul)（雀魂 → **天鳳形式** 変換）。
mjai-reviewer は天鳳形式を読むので、雀魂は天鳳形式へ変換して `mortal` に渡します。

1. 変換ツールを用意し、雀魂のアクセストークンを取得（各ツールの手順に従う）。
2. `.env` に設定:

   ```ini
   TENSOUL_PATH=/path/to/converter
   MAJSOUL_ACCESS_TOKEN=...
   ```

3. ツールの引数に合わせて **`MAJSOUL_FETCH_CMD`** で起動コマンドを上書き
   （`{id}`/`{out}`/`{token}` を置換。出力は**天鳳形式**にする）するか、
   `MahjongSoulSource.build_command()` を調整:

   ```ini
   MAJSOUL_FETCH_CMD=tensoul {id} -o {out} --token {token}
   ```

   変換後の天鳳形式ファイルを `jantama --log converted_tenhou.json` で解析できます。
4. 実行:

   ```bash
   jantama --url "https://game.mahjongsoul.com/?paipu=XXXXXX-..." --actor 0
   ```

> 変換ツールを用意しない場合でも、**変換済みの mjai ログを `--log`（CLI）や
> Discord への添付**で渡せば解析できます。`paipu=` URL の ID 抽出だけは
> ツール無しでも行えます（bot が「ログを添付してください」と案内する分岐に使用）。

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
