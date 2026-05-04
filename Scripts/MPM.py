import gradio as gr
import modules.scripts as scripts
from modules import script_callbacks, shared
import os
import secrets
from pathlib import Path

# requests is bundled with Stable Diffusion WebUI
import requests


API_SERVER_PORT = 19720


class ExternalPromptRequesterScript(scripts.Script):

    def title(self):
        return "External Prompt Requester (API)"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def ui(self, is_img2img):
        with gr.Group():
            with gr.Accordion("External Prompt Requester (API)", open=False):
                enabled = gr.Checkbox(
                    label="Enable External Prompt Request",
                    value=lambda: getattr(shared.opts, "external_prompt_enabled", False)
                )

                with gr.Row():
                    pos = gr.Textbox(
                        label="Positive Prompt Category",
                        value=lambda: getattr(shared.opts, "external_prompt_positive_category", "PositivePrompt")
                    )
                    neg = gr.Textbox(
                        label="Negative Prompt Category",
                        value=lambda: getattr(shared.opts, "external_prompt_negative_category", "NegativePrompt")
                    )

                timeout_seconds = gr.Slider(
                    label="Timeout (sec)",
                    minimum=5,
                    maximum=600,
                    value=lambda: getattr(shared.opts, "external_prompt_timeout_seconds", 240),
                    step=5,
                )

        return [enabled, pos, neg, timeout_seconds]

    def before_process(self, p, enabled, pos, neg, timeout_seconds):
        if not enabled:
            return

        positive_prompt, negative_prompt = self.request_external_prompts(
            pos,
            neg,
            timeout_seconds
        )

        if positive_prompt:
            p.prompt = positive_prompt
        if negative_prompt:
            p.negative_prompt = negative_prompt

    @staticmethod
    def _load_api_key():
        """Load API key from ~/.mpm/api_key file, fallback to MPM_API_KEY env var."""
        key_file = Path.home() / ".mpm" / "api_key"
        if key_file.exists():
            try:
                return key_file.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        return os.environ.get("MPM_API_KEY", "")

    def request_external_prompts(self, pos, neg, timeout_seconds):
        api_key = self._load_api_key()
        if not api_key:
            print("[ExternalPromptRequester] No API key found. Please open MPM and generate an API key in API Server Settings.")
            return "", ""

        session_id = f"sd-{secrets.token_hex(8)}"
        url = f"http://127.0.0.1:{API_SERVER_PORT}/api/v1/generate"

        try:
            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={"session_id": session_id},
                timeout=timeout_seconds,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            print(f"[ExternalPromptRequester] Cannot connect to API server at port {API_SERVER_PORT}. Is it running?")
            return "", ""
        except requests.exceptions.Timeout:
            print(f"[ExternalPromptRequester] Request timed out after {timeout_seconds}s")
            return "", ""
        except requests.exceptions.HTTPError as e:
            print(f"[ExternalPromptRequester] API error: {e.response.status_code} - {e.response.text}")
            return "", ""

        data = response.json()
        results = data.get("results", [])

        positive_prompt = next(
            (r["prompt"] for r in results if r.get("category_name") == pos and r.get("success")),
            ""
        )
        negative_prompt = next(
            (r["prompt"] for r in results if r.get("category_name") == neg and r.get("success")),
            ""
        )

        print(f"[ExternalPromptRequester] Generated prompts received (session: {session_id})")
        return positive_prompt, negative_prompt


def on_ui_settings():
    section = ("external_prompt", "External Prompt Requester")

    shared.opts.add_option(
        "external_prompt_enabled",
        shared.OptionInfo(False, "Enable External Prompt Request", gr.Checkbox, section=section)
    )

    shared.opts.add_option(
        "external_prompt_positive_category",
        shared.OptionInfo("PositivePrompt", "Positive Prompt Category", section=section)
    )

    shared.opts.add_option(
        "external_prompt_negative_category",
        shared.OptionInfo("NegativePrompt", "Negative Prompt Category", section=section)
    )

    shared.opts.add_option(
        "external_prompt_timeout_seconds",
        shared.OptionInfo(
            240,
            "Timeout (sec)",
            gr.Slider,
            {"minimum": 5, "maximum": 600, "step": 5},
            section=section,
        )
    )


script_callbacks.on_ui_settings(on_ui_settings)
