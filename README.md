# sd-webui-yumil-mpm

English | [日本語](README_ja.md)

A script extension for **Stable Diffusion WebUI Forge neo** that integrates with [Yumil MPM](https://github.com/maigonia/YumilMPM) — a prompt management tool for AI image generation.

## Requirements

- [Yumil MPM](https://github.com/maigonia/YumilMPM)

## Installation

### Install from URL (recommended)

1. Open the **Extensions** tab → **Install from URL** sub-tab in your Stable Diffusion WebUI.
2. Paste this URL into the **URL for extension's git repository** field:
   ```
   https://github.com/maigonia/sd-webui-yumil-mpm.git
   ```
3. Click **Install**.
4. Restart Stable Diffusion WebUI.

### Manual (alternative)

Clone this repository into your Stable Diffusion WebUI `extensions` folder:

```bash
cd stable-diffusion-webui/extensions
git clone https://github.com/maigonia/sd-webui-yumil-mpm.git
```

Restart Stable Diffusion WebUI after installation.

## Usage

### External Prompt Requester

Requests prompt generation from Yumil MPM before each image generation. While Yumil MPM's On-Demand Generation is active, every time you generate an image, a request is sent to Yumil MPM and the auto-generated prompts are applied automatically.

**Setup:**
1. Launch Yumil MPM.
2. Press the **Demand** button in the Generation panel (bottom-left) to enable On-Demand Generation.

**How to use:**
1. In the Stable Diffusion WebUI, open the **External Prompt Requester (API)** accordion in the script area.
2. Check **Enable External Prompt Request**.
3. Set the **Positive Prompt Category** and **Negative Prompt Category** to match the category names configured in Yumil MPM.
4. Adjust the **Timeout** as needed (default: 240 seconds).
5. Generate an image — the prompts from Yumil MPM will be applied automatically.

**Parameters:**
- `Enable External Prompt Request` — Enable/disable the extension
- `Positive Prompt Category` — Category name for the positive prompt (default: `PositivePrompt`)
- `Negative Prompt Category` — Category name for the negative prompt (default: `NegativePrompt`)
- `Timeout (sec)` — Request timeout in seconds (5–600, default: 240)

These settings can also be configured in **Settings > External Prompt Requester**.

### Sending reference images

External Prompt Requester can receive **reference images alongside prompts** from Yumil MPM and route them to ControlNet or img2img automatically. For details, see Yumil MPM's **Utility > Intermediate Tutorial > Sending Reference Images** section.

Received images are assigned to ControlNet units in the order they appear in the prompt (first block → unit 0, second → unit 1, ...). Only blocks with `Value(target=i2i)` are treated as img2img init images and are skipped when counting ControlNet slots. (This routing feature is unique to the WebUI extension — the ComfyUI version does not have it.)

| Specification | Destination |
|---|---|
| Omitted | Assigned to ControlNet units in appearance order |
| `Value(target=i2i)` | img2img init image (img2img mode only) |

**About ControlNet:**
- The ControlNet unit's module / model / weight etc. must be configured in the WebUI ControlNet panel beforehand. This extension only swaps the **image**.
- You do **not** need to check the unit's **Enable** checkbox — the extension enables it automatically.
- Reference images do not appear visually in the Forge Neo UI. Verify behavior via console output (e.g. `[ExternalPromptRequester] Applied image to CN unit 0`).

## Links

- [Yumil MPM (GitHub)](https://github.com/maigonia/YumilMPM)
- [ComfyUI version](https://github.com/maigonia/comfyui-yumil-mpm)
- [X (@YumilMpm)](https://x.com/YumilMpm)

## License

[MIT](LICENSE)
