import json
import os
import random
import re
import urllib.error
import urllib.request

try:
    import folder_paths
except ImportError:  # outside ComfyUI (tests)
    folder_paths = None

TAG_RE = re.compile(r"\{(\d+)\}")


def split_lines(text):
    """Turn multiline text into a list of entries.

    Empty lines and lines starting with '#' (comments) are ignored.
    """
    if not text:
        return []
    entries = []
    for line in str(text).splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            entries.append(line)
    return entries


def fill_template(template, lists, seed):
    """Replace {1}, {2}, ... in template with a random entry from lists["1"], lists["2"], ...

    The same tag number used twice in one template gets the same pick.
    Tags with no connected list (or an empty list) are left unchanged.
    """
    rng = random.Random(seed)
    picks = {}
    for num in sorted({int(n) for n in TAG_RE.findall(template)}):
        entries = split_lines(lists.get(str(num)))
        if entries:
            picks[str(num)] = rng.choice(entries)

    def repl(m):
        return picks.get(m.group(1), m.group(0))

    return TAG_RE.sub(repl, template)


class AnyKeyDict(dict):
    """Optional-inputs dict that accepts any input name.

    Lets the template node receive however many inputs ("1", "2", ...)
    the frontend has added, without declaring them in advance.
    """

    def __contains__(self, key):
        return True

    def __getitem__(self, key):
        if dict.__contains__(self, key):
            return dict.__getitem__(self, key)
        return ("STRING", {"forceInput": True})

    def get(self, key, default=None):
        return self[key]


class PromptGenLineList:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {
                    "multiline": True,
                    "default": "cat\ndog\ncow",
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("list",)
    FUNCTION = "run"
    CATEGORY = "PromptGen"
    DESCRIPTION = "A list of entries, one per line. Connect to a numbered input on PromptGen Template."

    def run(self, text):
        return (text,)


class PromptGenTemplate:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "template": ("STRING", {
                    "multiline": True,
                    "default": "The {1} sat on the {2}",
                }),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xFFFFFFFFFFFFFFFF,
                    "control_after_generate": True,
                }),
            },
            "optional": AnyKeyDict(),
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "run"
    CATEGORY = "PromptGen"
    DESCRIPTION = (
        "Replaces {1}, {2}, ... with a random line from the list plugged into input 1, 2, ... "
        "A new input slot appears each time you connect one."
    )

    def run(self, template, seed, **kwargs):
        lists = {k: v for k, v in kwargs.items() if k.isdigit()}
        result = fill_template(template, lists, seed)
        missing = sorted({m for m in TAG_RE.findall(result)}, key=int)
        if missing:
            print(f"[PromptGen] No list (or an empty list) for tag(s): {', '.join('{' + m + '}' for m in missing)}")
        return (result,)


class PromptGenShowText:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"forceInput": True}),
                "save_to_file": ("BOOLEAN", {"default": False}),
                "filename_prefix": ("STRING", {"default": "promptgen/text"}),
            },
            "optional": {
                "filename": ("STRING", {"forceInput": True}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "run"
    OUTPUT_NODE = True
    CATEGORY = "PromptGen"
    DESCRIPTION = (
        "Shows the text on the node and passes it through. Optionally saves it as a .txt file "
        "in ComfyUI's output folder. If 'filename' is connected (e.g. from PromptGen Counter) it is used "
        "after filename_prefix (prefix 'promptgen/before' + filename 'prompt_0001' gives promptgen/before_prompt_0001.txt); "
        "otherwise filename_prefix gives text_00001.txt style names. "
        "Repeated _ or - in names are collapsed to one."
    )

    def run(self, text, save_to_file, filename_prefix, filename=None):
        saved = "(not saved)"
        if save_to_file:
            if filename:
                path = save_text_named(text, combine_name(filename_prefix, filename))
            else:
                path = save_text(text, filename_prefix)
            print(f"[PromptGen] Saved prompt to {path}")
            try:
                saved = os.path.relpath(path, folder_paths.get_output_directory())
            except Exception:
                saved = path
        return {"ui": {"text": [text], "saved_file": [saved]}, "result": (text,)}


SEPARATOR_RUN_RE = re.compile(r"[_-]{2,}")


def clean_name(name):
    """Collapse runs like '__', '--' or '_-' into a single separator and trim them from the
    start/end of every folder and file name part."""
    parts = re.split(r"[\\/]+", str(name).strip())
    cleaned = []
    for part in parts:
        part = SEPARATOR_RUN_RE.sub(lambda m: m.group(0)[0], part).strip("_- ")
        if part:
            cleaned.append(part)
    return "/".join(cleaned)


def combine_name(prefix, name):
    """Put prefix in front of name: 'promptgen/before' + 'prompt_0001' -> 'promptgen/before_prompt_0001'.
    Folders from both are kept (a folder repeated at the start of name is not doubled)."""
    is_folder = str(prefix).strip().endswith(("/", "\\"))
    prefix, name = clean_name(prefix), clean_name(name)
    if not prefix:
        return name
    p_dir, p_base = (prefix, "") if is_folder else os.path.split(prefix)
    n_dir, n_base = os.path.split(name)
    if p_dir and n_dir.split("/")[0] == p_dir.split("/")[-1]:
        n_dir = "/".join(n_dir.split("/")[1:])
    folder = "/".join(x for x in (p_dir, n_dir) if x)
    base = f"{p_base}_{n_base}" if p_base else n_base
    return clean_name(f"{folder}/{base}" if folder else base)


def _resolve_in_output(relative, output_dir):
    out = os.path.abspath(output_dir)
    path = os.path.abspath(os.path.join(out, relative))
    if os.path.commonpath([out, path]) != out:
        raise ValueError(f"'{relative}' points outside the output folder.")
    return path


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def save_text(text, filename_prefix, output_dir=None):
    """Save to <output>/<prefix>_00001.txt, using the next free number."""
    if output_dir is None:
        output_dir = folder_paths.get_output_directory()
    prefix = clean_name(filename_prefix) or "promptgen/prompt"
    n = 1
    while True:
        path = _resolve_in_output(f"{prefix}_{n:05}.txt", output_dir)
        if not os.path.exists(path):
            return _write(path, text)
        n += 1


def save_text_named(text, filename, output_dir=None):
    """Save to <output>/<filename>.txt. filename may contain subfolders.
    Never overwrites: if the file exists, _2, _3 ... is added."""
    if output_dir is None:
        output_dir = folder_paths.get_output_directory()
    name = str(filename).strip()
    if name.lower().endswith(".txt"):
        name = name[:-4]
    name = clean_name(name)
    if not name:
        raise ValueError(f"Filename '{filename}' is empty after cleaning.")
    path = _resolve_in_output(name + ".txt", output_dir)
    n = 2
    while os.path.exists(path):
        path = _resolve_in_output(f"{name}_{n}.txt", output_dir)
        n += 1
    return _write(path, text)


# In-memory only (nothing on disk). Per node: the widget value seen last time and the next number.
_RUN_COUNTERS = {}


def take_number(key, widget_value, auto_increment):
    """Number to use for this run.

    Every execution moves on by one, even when a batch of runs was queued with the same widget value.
    When the widget shows a different value than last time (you typed one, or the UI moved it on),
    counting continues from the widget value.
    """
    if not auto_increment:
        _RUN_COUNTERS.pop(key, None)
        return widget_value
    state = _RUN_COUNTERS.get(key)
    if state is None or state["widget"] != widget_value:
        n = widget_value
    else:
        n = state["next"]
    _RUN_COUNTERS[key] = {"widget": widget_value, "next": n + 1}
    return n


class PromptGenCounter:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prefix": ("STRING", {"default": "prompt"}),
                "digits": ("INT", {"default": 4, "min": 1, "max": 12}),
                "current_number": ("INT", {"default": 1, "min": 0, "max": 0x7FFFFFFFFFFFFFFF}),
                "auto_increment": ("BOOLEAN", {"default": True, "label_on": "on", "label_off": "off"}),
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("INT", "STRING")
    RETURN_NAMES = ("number", "name")
    FUNCTION = "run"
    CATEGORY = "PromptGen"
    DESCRIPTION = (
        "Outputs current_number and 'prefix_0001'. With auto_increment on, the current_number field goes up by 1 "
        "every time you queue the workflow. Type a number to jump to it. Nothing is stored on disk; "
        "the number is saved with the workflow."
    )

    @classmethod
    def IS_CHANGED(cls, auto_increment=True, **kwargs):
        return float("nan") if auto_increment else ""  # with auto_increment: never cached, runs every time

    def run(self, prefix, digits, current_number, auto_increment, unique_id=None):
        n = take_number(("counter", unique_id), current_number, auto_increment)
        number = str(n).zfill(digits)
        name = clean_name(f"{prefix}_{number}" if prefix else number)
        ui = {"next_number": [n + 1 if auto_increment else n]}
        return {"ui": ui, "result": (n, name)}


def resolve_folder(folder):
    """Absolute path, or a path relative to ComfyUI's output folder."""
    folder = os.path.expanduser(str(folder).strip().strip('"'))
    if not os.path.isabs(folder) and folder_paths is not None:
        folder = os.path.join(folder_paths.get_output_directory(), folder)
    return os.path.abspath(folder)


def list_text_files(folder):
    if not os.path.isdir(folder):
        raise FileNotFoundError(f"Folder not found: {folder}")
    names = [f for f in os.listdir(folder) if f.lower().endswith(".txt") and os.path.isfile(os.path.join(folder, f))]
    return sorted(names, key=str.lower)


class PromptGenBatchText:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder": ("STRING", {"default": "promptgen"}),
                "index": ("INT", {"default": 0, "min": 0, "max": 0x7FFFFFFF}),
                "auto_increment": ("BOOLEAN", {"default": True, "label_on": "on", "label_off": "off"}),
                "when_done": (["stop", "start over"], {"default": "stop"}),
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("STRING", "STRING", "INT", "INT")
    RETURN_NAMES = ("text", "name", "index", "total")
    FUNCTION = "run"
    CATEGORY = "PromptGen"
    DESCRIPTION = (
        "Loads one .txt file from a folder (sorted by name). index 0 is the first file. With auto_increment on, "
        "index goes up by 1 every time you queue, so each run gets the next file. 'folder' can be a full path "
        "or a path inside ComfyUI's output folder (e.g. promptgen). Outputs the text and the file name without .txt."
    )

    @classmethod
    def IS_CHANGED(cls, folder, index, auto_increment=True, **kwargs):
        if auto_increment:
            return float("nan")  # never cached: next file every run
        # Fixed index: re-run only when the folder's files change.
        try:
            path = resolve_folder(folder)
            files = list_text_files(path)
            stamp = [(f, os.path.getmtime(os.path.join(path, f))) for f in files]
        except Exception as e:
            stamp = str(e)
        return f"{index}|{stamp}"

    def run(self, folder, index, auto_increment, when_done, unique_id=None):
        path = resolve_folder(folder)
        files = list_text_files(path)
        total = len(files)
        if total == 0:
            raise FileNotFoundError(f"No .txt files in {path}")
        index = take_number(("batch", unique_id), index, auto_increment)
        i = index
        if i >= total:
            if when_done == "start over":
                i = i % total
            else:
                raise RuntimeError(
                    f"All {total} files in {path} are done (index {index}). Set index back to 0 to start again."
                )
        fname = files[i]
        with open(os.path.join(path, fname), "r", encoding="utf-8-sig") as f:
            text = f.read().strip()
        name = os.path.splitext(fname)[0]
        next_index = i + 1 if auto_increment else index
        if auto_increment and when_done == "start over":
            next_index %= total
        return {
            "ui": {"next_number": [next_index], "loaded": [f"{i + 1}/{total}: {fname}"]},
            "result": (text, name, i, total),
        }


SAMPLER_KEYS = ["seed", "noise_seed", "steps", "cfg", "sampler_name", "scheduler", "denoise",
                "add_noise", "start_at_step", "end_at_step", "return_with_leftover_noise"]
MODEL_LOADERS = {"CheckpointLoaderSimple": "ckpt_name", "UNETLoader": "unet_name", "CheckpointLoader": "ckpt_name"}


def _resolve_value(prompt, value, depth=0):
    """Follow a link [node_id, slot] to a plain value where possible."""
    if not (isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)):
        return value
    node = prompt.get(value[0], {})
    inputs = node.get("inputs", {})
    label = f"(from {node.get('class_type', '?')} node {value[0]})"
    if depth >= 5:
        return label
    for k in ("value", "seed", "noise_seed", "int", "float", "number"):
        if k in inputs:
            return _resolve_value(prompt, inputs[k], depth + 1)
    if len(inputs) == 1:
        return _resolve_value(prompt, next(iter(inputs.values())), depth + 1)
    return label


def describe_settings(prompt, image=None):
    lines = []
    prompt = prompt or {}
    for nid, node in sorted(prompt.items(), key=lambda kv: (len(kv[0]), kv[0])):
        ctype = node.get("class_type", "")
        inputs = node.get("inputs", {})
        if ctype.startswith("KSampler") or ("sampler_name" in inputs and "steps" in inputs):
            lines.append(f"{ctype} (node {nid})")
            for k in SAMPLER_KEYS:
                if k in inputs:
                    lines.append(f"  {k}: {_resolve_value(prompt, inputs[k])}")
        elif ctype in MODEL_LOADERS and MODEL_LOADERS[ctype] in inputs:
            lines.append(f"Model: {_resolve_value(prompt, inputs[MODEL_LOADERS[ctype]])}")
    if image is not None:
        b, h, w = image.shape[0], image.shape[1], image.shape[2]
        lines.append(f"Resolution: {w} x {h} (batch {b})")
    else:
        for nid, node in prompt.items():
            inputs = node.get("inputs", {})
            if "width" in inputs and "height" in inputs and "Latent" in node.get("class_type", ""):
                w = _resolve_value(prompt, inputs["width"])
                h = _resolve_value(prompt, inputs["height"])
                b = _resolve_value(prompt, inputs.get("batch_size", 1))
                lines.append(f"Resolution: {w} x {h} (batch {b}, from {node['class_type']} node {nid})")
    return "\n".join(lines) if lines else "(no KSampler found in this workflow)"


class PromptGenSaveSettings:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "filename_prefix": ("STRING", {"default": "promptgen/settings"}),
            },
            "optional": {
                "image": ("IMAGE",),
                "filename": ("STRING", {"forceInput": True}),
            },
            "hidden": {"prompt": "PROMPT"},
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("settings",)
    FUNCTION = "run"
    OUTPUT_NODE = True
    CATEGORY = "PromptGen"
    DESCRIPTION = (
        "Saves the settings of every KSampler in this run (seed, steps, cfg, sampler, scheduler, denoise), the model "
        "and the image resolution to a .txt file. Connect the decoded image so it saves after the image is made and "
        "records the real size. filename/filename_prefix work like PromptGen Show / Save Text."
    )

    def run(self, filename_prefix, image=None, filename=None, prompt=None):
        text = describe_settings(prompt, image)
        if filename:
            path = save_text_named(text, combine_name(filename_prefix, filename))
        else:
            path = save_text(text, filename_prefix)
        print(f"[PromptGen] Saved settings to {path}")
        try:
            saved = os.path.relpath(path, folder_paths.get_output_directory())
        except Exception:
            saved = path
        return {"ui": {"text": [text], "saved_file": [saved]}, "result": (text,)}


DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "hf.co/TrevorJS/gemma-4-E2B-it-uncensored-GGUF:latest"
NO_MODELS = "(no models found - is Ollama running?)"
THINK_RE = re.compile(r"<think>.*?</think>|<\|channel>.*?<channel\|>", re.DOTALL)
THINK_END_MARKERS = ("</think>", "<channel|>")


def strip_thinking(text):
    """Remove reasoning/thinking sections some models put before the answer."""
    text = THINK_RE.sub("", text)
    for marker in THINK_END_MARKERS:  # end marker without a matching start
        if marker in text:
            text = text.rsplit(marker, 1)[1]
    return text.strip()


def ollama_models(url=DEFAULT_OLLAMA_URL, timeout=2):
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/tags", timeout=timeout) as r:
            data = json.load(r)
        return sorted(m["name"] for m in data.get("models", []))
    except Exception:
        return []


def _post_json(url, body, timeout):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def ollama_generate(url, model, instruction, prompt, seed, temperature, thinking=False, timeout=600):
    body = {
        "model": model,
        "system": instruction,
        "prompt": prompt,
        "stream": False,
        "think": bool(thinking),
        "options": {"seed": seed % (2**31), "temperature": temperature},
    }
    endpoint = url.rstrip("/") + "/api/generate"
    try:
        try:
            data = _post_json(endpoint, body, timeout)
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")
            if e.code == 400 and "think" in msg.lower():
                # Older Ollama or a model without thinking support: retry without the flag.
                body.pop("think")
                data = _post_json(endpoint, body, timeout)
            else:
                raise RuntimeError(f"Ollama error {e.code}: {msg}") from e
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Ollama error {e.code}: {e.read().decode('utf-8', 'replace')}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Could not reach Ollama at {url}: {e.reason}") from e
    return strip_thinking(data.get("response", ""))


class PromptGenOllamaRewrite:
    @classmethod
    def INPUT_TYPES(cls):
        models = ollama_models() or [NO_MODELS]
        return {
            "required": {
                "prompt": ("STRING", {"forceInput": True}),
                "instruction": ("STRING", {
                    "multiline": True,
                    "default": (
                        "Rewrite the user's text into a single detailed image generation prompt. "
                        "Keep the original subjects. Reply with the prompt only, no explanations."
                    ),
                }),
                "model": (models, {"default": DEFAULT_OLLAMA_MODEL if DEFAULT_OLLAMA_MODEL in models else models[0]}),
                "ollama_url": ("STRING", {"default": DEFAULT_OLLAMA_URL}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.05}),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xFFFFFFFFFFFFFFFF,
                    "control_after_generate": True,
                }),
                "thinking": ("BOOLEAN", {"default": False, "label_on": "let model think", "label_off": "no thinking (faster)"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "run"
    CATEGORY = "PromptGen"
    DESCRIPTION = "Sends the prompt to an Ollama model with your instruction and outputs the rewritten text."

    def run(self, prompt, instruction, model, ollama_url, temperature, seed, thinking=False):
        if model == NO_MODELS:
            raise RuntimeError(
                f"No Ollama models found at {ollama_url}. Start Ollama, pull a model "
                "(e.g. 'ollama pull llama3.1'), then press R in ComfyUI to refresh the list."
            )
        return (ollama_generate(ollama_url, model, instruction, prompt, seed, temperature, thinking),)


NODE_CLASS_MAPPINGS = {
    "PromptGenSaveSettings": PromptGenSaveSettings,
    "PromptGenBatchText": PromptGenBatchText,
    "PromptGenCounter": PromptGenCounter,
    "PromptGenOllamaRewrite": PromptGenOllamaRewrite,
    "PromptGenShowText": PromptGenShowText,
    "PromptGenLineList": PromptGenLineList,
    "PromptGenTemplate": PromptGenTemplate,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PromptGenSaveSettings": "PromptGen Save Settings",
    "PromptGenBatchText": "PromptGen Batch Text Loader",
    "PromptGenCounter": "PromptGen Counter",
    "PromptGenOllamaRewrite": "PromptGen Ollama Rewrite",
    "PromptGenShowText": "PromptGen Show / Save Text",
    "PromptGenLineList": "PromptGen Line List",
    "PromptGenTemplate": "PromptGen Template",
}


# Small API used by the "Queue all files" button: how many .txt files are in a folder.
try:
    from aiohttp import web
    from server import PromptServer

    @PromptServer.instance.routes.get("/promptgen/count_files")
    async def _promptgen_count_files(request):
        try:
            path = resolve_folder(request.query.get("folder", ""))
            return web.json_response({"total": len(list_text_files(path)), "folder": path})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)
except Exception:  # not running inside ComfyUI (tests)
    pass
