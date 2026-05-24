# sd-webui-yumil-mpm

[English](README.md) | 日本語

[Yumil MPM](https://github.com/maigonia/YumilMPM) と連携する **Stable Diffusion WebUI Forge neo** 用の拡張スクリプトです。AI 画像生成のプロンプト管理を効率化します。

## 必要なもの

- [Yumil MPM](https://github.com/maigonia/YumilMPM)

## インストール

### Install from URL（推奨）

1. Stable Diffusion WebUI の **Extensions** タブ → **Install from URL** サブタブを開きます。
2. **URL for extension's git repository** 欄に以下の URL を貼り付けます:
   ```
   https://github.com/maigonia/sd-webui-yumil-mpm.git
   ```
3. **Install** ボタンをクリックします。
4. Stable Diffusion WebUI を再起動します。

### 手動インストール（代替）

Stable Diffusion WebUI の `extensions` フォルダにクローンします:

```bash
cd stable-diffusion-webui/extensions
git clone https://github.com/maigonia/sd-webui-yumil-mpm.git
```

インストール後、Stable Diffusion WebUI を再起動してください。

## 使い方

### External Prompt Requester

画像生成の直前に Yumil MPM へプロンプト生成をリクエストします。Yumil MPM の On-Demand Generation が有効な間、画像を生成するたびに Yumil MPM へリクエストが送られ、自動生成されたプロンプトが適用されます。

**セットアップ:**
1. Yumil MPM を起動します。
2. 左下の Generation パネル内にある **Demand** ボタンを押して On-Demand Generation を有効にします。

**使い方:**
1. Stable Diffusion WebUI のスクリプトエリアにある **External Prompt Requester (API)** のアコーディオンを開きます。
2. **Enable External Prompt Request** にチェックを入れます。
3. **Positive Prompt Category** と **Negative Prompt Category** に、Yumil MPM で設定したカテゴリ名を入力します。
4. 必要に応じて **Timeout** を調整します（デフォルト: 240秒）。
5. 画像を生成すると、Yumil MPM からのプロンプトが自動的に適用されます。

**パラメータ:**
- `Enable External Prompt Request` — 拡張機能の有効/無効
- `Positive Prompt Category` — ポジティブプロンプトのカテゴリ名（デフォルト: `PositivePrompt`）
- `Negative Prompt Category` — ネガティブプロンプトのカテゴリ名（デフォルト: `NegativePrompt`）
- `Timeout (sec)` — リクエストタイムアウト秒数（5〜600、デフォルト: 240）
- `Auto-resize output to first reference image aspect ratio` — 最初の参照画像のアスペクト比に合わせて出力サイズを自動調整（デフォルト: オフ）
- `Target width + height (sum)` — 自動リサイズ時の幅 + 高さの合計値（512〜8192、デフォルト: 2048）

これらの設定は **Settings > External Prompt Requester** からも変更できます。

### 参照画像の送信

External Prompt Requester は、Yumil MPM から **プロンプトに加えて参照画像** を受け取り、ControlNet や img2img に自動で流し込めます。詳しくは、Yumil MPM の **Utility > チュートリアル中級編 > 参照画像の送り方** を参照してください。

受け取った画像は、プロンプト中に現れた順に ControlNet ユニットへ自動的に割り当てられます（1 つ目 → ユニット 0、2 つ目 → ユニット 1、...）。`Value(target=i2i)` を指定したブロックだけは img2img の入力画像として扱われ、ControlNet の割り当て順には含まれません（ComfyUI 版にはない、本拡張独自の機能です）。

| 指定 | 送り先 |
|---|---|
| 省略時 | 登場順に ControlNet ユニットへ |
| `Value(target=i2i)` | img2img の入力画像（img2img モードのときのみ） |

**ControlNet について:**
- module / model / weight などの ControlNet 側設定は、事前に WebUI の ControlNet パネルで構成しておいてください。本拡張は **画像のみ** を差し替えます。
- ControlNet ユニットの **Enable チェックは不要** です（本拡張が自動で有効化します）。
- 参照画像は Forge Neo の UI 上には反映されません。動作確認はコンソール出力（`[ExternalPromptRequester] Applied image to CN unit 0` 等のメッセージ）で行ってください。

**自動リサイズについて:**

`Auto-resize output to first reference image aspect ratio` を有効にすると、最初に読み込まれた参照画像（i2i / ControlNet どちらでも可）の縦横比に合わせて、出力サイズが自動調整されます。`Target width + height (sum)` で全体の大きさを指定できます（SDXL は 2048 がおすすめ）。

## リンク

- [Yumil MPM (GitHub)](https://github.com/maigonia/YumilMPM)
- [ComfyUI 版](https://github.com/maigonia/comfyui-yumil-mpm)
- [X (@YumilMpm)](https://x.com/YumilMpm)

## ライセンス

[MIT](LICENSE)
