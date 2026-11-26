"""Node registry. Node IDs must not change: saved workflows refer to them."""

from .nodes.batch import PromptGenBatchImage, PromptGenBatchText
from .nodes.counter import PromptGenCounter
from .nodes.ollama import PromptGenOllamaRewrite
from .nodes.settings import PromptGenSaveSettings
from .nodes.text import PromptGenLineList, PromptGenShowText, PromptGenTemplate

_NODES = {
    "PromptGenLineList": (PromptGenLineList, "PromptGen Line List"),
    "PromptGenTemplate": (PromptGenTemplate, "PromptGen Template"),
    "PromptGenOllamaRewrite": (PromptGenOllamaRewrite, "PromptGen Ollama Rewrite"),
    "PromptGenShowText": (PromptGenShowText, "PromptGen Show / Save Text"),
    "PromptGenCounter": (PromptGenCounter, "PromptGen Counter"),
    "PromptGenBatchText": (PromptGenBatchText, "PromptGen Batch Text Loader"),
    "PromptGenBatchImage": (PromptGenBatchImage, "PromptGen Batch Image Loader"),
    "PromptGenSaveSettings": (PromptGenSaveSettings, "PromptGen Save Settings"),
}

NODE_CLASS_MAPPINGS = {node_id: cls for node_id, (cls, _) in _NODES.items()}
NODE_DISPLAY_NAME_MAPPINGS = {node_id: name for node_id, (_, name) in _NODES.items()}
