"""Ollama Rewrite."""

from __future__ import annotations

from ..comfy import CATEGORY
from ..core import ollama_client

NO_MODELS = "(no models found - is Ollama running?)"
DEFAULT_INSTRUCTION = (
    "Rewrite the user's text into a single detailed image generation prompt. "
    "Keep the original subjects. Reply with the prompt only, no explanations."
)


class PromptGenOllamaRewrite:
    DESCRIPTION = "Sends the prompt to an Ollama model with your instruction and outputs the rewritten text."
    CATEGORY = CATEGORY
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        # The list is read from the default URL; the first installed model is the default.
        models = ollama_client.list_models() or [NO_MODELS]
        return {
            "required": {
                "prompt": ("STRING", {"forceInput": True}),
                "instruction": ("STRING", {"multiline": True, "default": DEFAULT_INSTRUCTION}),
                "model": (models,),
                "ollama_url": ("STRING", {"default": ollama_client.DEFAULT_URL}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.05}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF, "control_after_generate": True}),
                "thinking": ("BOOLEAN", {"default": False, "label_on": "let model think", "label_off": "no thinking (faster)"}),
            }
        }

    def run(self, prompt, instruction, model, ollama_url, temperature, seed, thinking=False):
        if model == NO_MODELS:
            raise RuntimeError(
                f"No Ollama models found at {ollama_url}. Start Ollama, pull a model "
                "(e.g. 'ollama pull llama3.1'), then press R in ComfyUI to refresh the list."
            )
        return (ollama_client.generate(ollama_url, model, instruction, prompt, seed, temperature, thinking),)
