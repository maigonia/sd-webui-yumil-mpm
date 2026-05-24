import gradio as gr
import modules.scripts as scripts
from modules import script_callbacks, shared
import importlib
import os
import secrets
import sys
from pathlib import Path

import numpy as np
from PIL import Image
import requests

# Make sibling module importable
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from yumil_parser import parse_prompt


API_SERVER_PORT = 19720
LOG_PREFIX = "[ExternalPromptRequester]"


def _parse_value_kvs(value_str):
    """Parse 'k1=v1,k2=v2' style string into a dict (lowercased keys)."""
    if not value_str:
        return {}
    out = {}
    for pair in value_str.split(","):
        pair = pair.strip()
        if "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        out[k.strip().lower()] = v.strip()
    return out


def _load_image(path):
    if not path:
        return None
    if not os.path.isfile(path):
        print(f"{LOG_PREFIX} Image not found: {path}")
        return None
    try:
        img = Image.open(path)
        img.load()
        return img
    except Exception as e:
        print(f"{LOG_PREFIX} Failed to load '{path}': {e}")
        return None


def _calc_size_by_total(width, height, target_total):
    """Aspect-ratio preserving size where width+height == target_total, rounded to multiples of 8.

    Mirrors comfyui-yumil-mpm/nodes/image.py:calc_size_by_total.
    """
    aspect = width / height
    new_h = target_total / (1 + aspect)
    new_w = target_total - new_h
    new_w = max(8, round(new_w / 8) * 8)
    new_h = max(8, round(new_h / 8) * 8)
    return (new_w, new_h)


def _get_cn_units(p):
    """Return list of ControlNet unit objects for *this* processing job.

    Tries (in order):
      1. Forge Neo / current Forge: read from p.script_args[script.args_from:args_to]
         where script.title() == "ControlNet". Units are ControlNetUnit objects;
         mutating them in place propagates to CN's process() call.
      2. Legacy A1111 / lllyasviel Forge: external_code.get_all_units_in_processing(p).

    Returns (units_list, writeback_fn) where writeback_fn(units) is optional.
    Returns (None, None) if CN isn't available.
    """
    # ---- Strategy 1: Forge Neo / current Forge ----
    scripts_runner = getattr(p, "scripts", None)
    alwayson = getattr(scripts_runner, "alwayson_scripts", None) if scripts_runner else None
    if alwayson:
        for script in alwayson:
            try:
                title = script.title()
            except Exception:
                continue
            if title != "ControlNet":
                continue
            args_from = getattr(script, "args_from", None)
            args_to = getattr(script, "args_to", None)
            script_args = getattr(p, "script_args", None)
            if args_from is None or args_to is None or script_args is None:
                continue
            units = list(script_args[args_from:args_to])
            if not units:
                continue
            return units, None  # mutations to units propagate

    # ---- Strategy 2: legacy external_code API ----
    for name, mod in list(sys.modules.items()):
        if mod is None:
            continue
        if not (name.endswith(".external_code") or name == "external_code"):
            continue
        if "control" not in name.lower():
            continue
        if hasattr(mod, "get_all_units_in_processing"):
            try:
                units = mod.get_all_units_in_processing(p)
            except Exception:
                continue
            update_fn = getattr(mod, "update_cn_script_in_processing", None)
            writeback = (lambda us, _fn=update_fn: _fn(p, us)) if update_fn else None
            return units, writeback
    for candidate in ("lib_controlnet.external_code", "internal_controlnet.external_code"):
        try:
            mod = importlib.import_module(candidate)
        except Exception:
            continue
        if not hasattr(mod, "get_all_units_in_processing"):
            continue
        try:
            units = mod.get_all_units_in_processing(p)
        except Exception:
            continue
        update_fn = getattr(mod, "update_cn_script_in_processing", None)
        writeback = (lambda us, _fn=update_fn: _fn(p, us)) if update_fn else None
        return units, writeback

    return None, None


def _set_cn_unit_image(unit, pil_image):
    np_img = np.array(pil_image.convert("RGB"))
    current = getattr(unit, "image", None)
    if isinstance(current, dict):
        unit.image = {"image": np_img, "mask": current.get("mask")}
    else:
        unit.image = np_img


def _apply_to_i2i(p, pil_image):
    if not hasattr(p, "init_images"):
        print(f"{LOG_PREFIX} target=i2i ignored (not in img2img mode)")
        return False
    p.init_images = [pil_image]
    print(f"{LOG_PREFIX} Applied image to img2img init_images")
    return True


def _apply_to_cn(p, unit_index, pil_image):
    units, writeback = _get_cn_units(p)
    if units is None:
        print(f"{LOG_PREFIX} ControlNet not loaded; target=cn{unit_index} skipped")
        return False
    if unit_index >= len(units):
        print(f"{LOG_PREFIX} CN unit {unit_index} not available (have {len(units)} units)")
        return False
    unit = units[unit_index]
    try:
        _set_cn_unit_image(unit, pil_image)
        unit.enabled = True
    except Exception as e:
        print(f"{LOG_PREFIX} Failed to set CN unit {unit_index}: {e}")
        return False
    if writeback is not None:
        try:
            writeback(units)
        except Exception as e:
            print(f"{LOG_PREFIX} CN writeback failed: {e}")
    print(f"{LOG_PREFIX} Applied image to CN unit {unit_index}")
    return True


def _apply_blocks(p, blocks, resize_enabled=False, resize_target_total=2048):
    """Route each block's first image path to a target.

    Blocks with Value(target=i2i) go to img2img init_images.
    All other blocks are assigned to ControlNet units in the order they appear
    (first block -> unit 0, second -> unit 1, ...).

    If resize_enabled, overrides p.width/p.height to match the aspect ratio of
    the *first successfully loaded* reference image, with width+height summing
    to resize_target_total (rounded to multiples of 8).
    """
    cn_counter = 0
    first_img = None
    for block in blocks:
        if not block.path:
            continue
        paths = [s.strip() for s in block.path.split(",") if s.strip()]
        if not paths:
            continue
        if len(paths) > 1:
            print(f"{LOG_PREFIX} Block has {len(paths)} paths; using first only")
        img = _load_image(paths[0])
        if img is None:
            continue
        if first_img is None:
            first_img = img
        kvs = _parse_value_kvs(block.value)
        target = kvs.get("target", "").strip().lower()
        if target == "i2i":
            _apply_to_i2i(p, img)
        else:
            _apply_to_cn(p, cn_counter, img)
            cn_counter += 1

    if resize_enabled and first_img is not None:
        ref_w, ref_h = first_img.size
        new_w, new_h = _calc_size_by_total(ref_w, ref_h, resize_target_total)
        old_w, old_h = p.width, p.height
        p.width = new_w
        p.height = new_h
        print(f"{LOG_PREFIX} Output size: {old_w}x{old_h} -> {new_w}x{new_h} (ref={ref_w}x{ref_h}, total={resize_target_total})")


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

                with gr.Row():
                    resize_enabled = gr.Checkbox(
                        label="Auto-resize output to first reference image aspect ratio",
                        value=lambda: getattr(shared.opts, "external_prompt_resize_enabled", False)
                    )
                    resize_target_total = gr.Slider(
                        label="Target width + height (sum)",
                        minimum=512,
                        maximum=8192,
                        value=lambda: getattr(shared.opts, "external_prompt_resize_target_total", 2048),
                        step=64,
                    )

        return [enabled, pos, neg, timeout_seconds, resize_enabled, resize_target_total]

    def before_process(self, p, enabled, pos, neg, timeout_seconds, resize_enabled, resize_target_total):
        if not enabled:
            return

        positive_prompt, negative_prompt = self.request_external_prompts(
            pos,
            neg,
            timeout_seconds
        )

        if positive_prompt:
            try:
                result = parse_prompt(positive_prompt)
                p.prompt = result.clean_text
                if result.blocks:
                    _apply_blocks(p, result.blocks, resize_enabled, resize_target_total)
            except Exception as e:
                print(f"{LOG_PREFIX} Positive prompt processing failed: {e}")
                p.prompt = positive_prompt

        if negative_prompt:
            try:
                result = parse_prompt(negative_prompt)
                p.negative_prompt = result.clean_text
            except Exception as e:
                print(f"{LOG_PREFIX} Negative prompt processing failed: {e}")
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
            print(f"{LOG_PREFIX} No API key found. Please open MPM and generate an API key in API Server Settings.")
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
            print(f"{LOG_PREFIX} Cannot connect to API server at port {API_SERVER_PORT}. Is it running?")
            return "", ""
        except requests.exceptions.Timeout:
            print(f"{LOG_PREFIX} Request timed out after {timeout_seconds}s")
            return "", ""
        except requests.exceptions.HTTPError as e:
            print(f"{LOG_PREFIX} API error: {e.response.status_code} - {e.response.text}")
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

        print(f"{LOG_PREFIX} Generated prompts received (session: {session_id})")
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

    shared.opts.add_option(
        "external_prompt_resize_enabled",
        shared.OptionInfo(False, "Auto-resize output to first reference image aspect ratio", gr.Checkbox, section=section)
    )

    shared.opts.add_option(
        "external_prompt_resize_target_total",
        shared.OptionInfo(
            2048,
            "Target width + height (sum) for auto-resize",
            gr.Slider,
            {"minimum": 512, "maximum": 8192, "step": 64},
            section=section,
        )
    )


script_callbacks.on_ui_settings(on_ui_settings)
