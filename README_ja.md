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

これらの設定は **Settings > External Prompt Requester** からも変更できます。

## リンク

- [Yumil MPM (GitHub)](https://github.com/maigonia/YumilMPM)
- [ComfyUI 版](https://github.com/maigonia/comfyui-yumil-mpm)
- [X (@YumilMpm)](https://x.com/YumilMpm)

## ライセンス

[MIT](LICENSE)
