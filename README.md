# comfyui-promptgen

Custom nodes for [ComfyUI](https://github.com/comfyanonymous/ComfyUI) that build random prompts from your own lists of text snippets. You can also have a local LLM rewrite the prompts through [Ollama](https://ollama.com), save the prompts and the generation settings as text files, and later load those files back in to make an image for each one.

All nodes are in the **PromptGen** category of the node menu.

| Node | What it does |
|---|---|
| [PromptGen Line List](#promptgen-line-list) | A list of entries, one per line |
| [PromptGen Template](#promptgen-template) | Fills `{1}`, `{2}`, ... in a template with random lines from the lists |
| [PromptGen Ollama Rewrite](#promptgen-ollama-rewrite) | Lets an Ollama model rewrite a prompt using your instruction |
| [PromptGen Show / Save Text](#promptgen-show--save-text) | Shows text on the node and can save it as a `.txt` file |
| [PromptGen Counter](#promptgen-counter) | A number that goes up with every run, plus a padded name like `prompt_0001` |
| [PromptGen Batch Text Loader](#promptgen-batch-text-loader) | Loads the next `.txt` file from a folder on every run |
| [PromptGen Save Settings](#promptgen-save-settings) | Saves the prompts, KSampler settings, seed, model and resolution as a `.json` file |

## Installation

1. Clone or copy this repository into `ComfyUI/custom_nodes/`:
   ```
   cd ComfyUI/custom_nodes
   git clone <this repository's URL> comfyui-promptgen
   ```
2. Restart ComfyUI and refresh the browser page.

You don't need any extra Python packages. The Ollama node needs [Ollama](https://ollama.com) running, by default at `http://localhost:11434`, with at least one model pulled (for example `ollama pull llama3.1`).

None of the nodes keep their own state on disk. Counters live in the workflow and in memory. The only files written are the `.txt` and `.json` files you ask the save nodes to write, and they always go inside ComfyUI's `output` folder.

---

## Nodes

### PromptGen Line List

A text box where every line is one entry. Connect it to a numbered input on **PromptGen Template**.

| Input | Type | Description |
|---|---|---|
| `text` | STRING (multiline) | One entry per line. Empty lines and lines starting with `#` are ignored. |

| Output | Type | Description |
|---|---|---|
| `list` | STRING | The text as it is. The Template node picks the random line. |

Any other node that outputs a STRING can be used as a list too.

### PromptGen Template

Write a prompt with numbered tags, for example `The {1} sat on the {2}`, and connect a list to each numbered input. On every run, each `{N}` is replaced with a random line from the list connected to input `N`.

The inputs grow by themselves: when you connect the last free input, a new one appears.

| Input | Type | Description |
|---|---|---|
| `template` | STRING (multiline) | Your prompt, with `{1}`, `{2}`, ... where random entries should go. |
| `seed` | INT | Controls the random picks. Set the control to *randomize* for new picks every run, or *fixed* to repeat the same prompt. |
| `1`, `2`, ... | STRING | The lists, one per tag number. |

| Output | Type | Description |
|---|---|---|
| `prompt` | STRING | The finished prompt. Connect it to a CLIP Text Encode `text` input, or to Ollama Rewrite. |

Notes:
- If the same tag appears more than once (`{1} ... {1}`), every copy gets the same pick.
- A tag with no list connected, or with an empty list, is left as it is (for example `{3}`), and a warning is printed in the console.

### PromptGen Ollama Rewrite

Sends a prompt to a local Ollama model, with your instruction as the system prompt, and outputs the reply.

| Input | Type | Description |
|---|---|---|
| `prompt` | STRING | The text to rewrite, for example from the Template node. |
| `instruction` | STRING (multiline) | What the model should do with it. |
| `model` | list | The models installed in Ollama. Press **R** in ComfyUI to refresh the list after pulling a new model. |
| `ollama_url` | STRING | Ollama's address. Default `http://localhost:11434`. |
| `temperature` | FLOAT | 0 to 2. Higher values give more varied rewrites. Default 0.7. |
| `seed` | INT | Passed to the model. Changing it gives a new rewrite for the same prompt. Not every model gives the same output for the same seed. |
| `thinking` | BOOLEAN | Off by default: the model is asked not to "think" first. This makes it faster and keeps the reasoning out of the output. Turn it on only for models where you want that. |

| Output | Type | Description |
|---|---|---|
| `text` | STRING | The rewritten prompt. Any thinking sections (`<think>…</think>` or `<|channel>…<channel|>`) are removed. |

Notes:
- The `model` list is read from `http://localhost:11434` when ComfyUI loads the node list. If Ollama wasn't running then, the list shows *"(no models found - is Ollama running?)"*. Start Ollama and press **R**.
- Example instruction for a style template:
  ```
  You write prompts for an image generator. Turn the user's short idea into one detailed
  paragraph in the same style, structure and length as the example below. Keep the user's
  subject, invent fitting details for pose, expression, clothing, setting, lighting,
  background and colours. Reply with the finished prompt only: one paragraph, no title,
  no quotes, no lists, no explanation.

  Example of the style:
  A 2d european comicbook illustration with clearly recognizable lineart of ...
  ```

### PromptGen Show / Save Text

Shows the incoming text on the node, passes it on, and can save it as a `.txt` file in ComfyUI's `output` folder. After each run the node also shows which file it saved to.

| Input | Type | Description |
|---|---|---|
| `text` | STRING | The text to show or save. |
| `save_to_file` | BOOLEAN | Turn on to write a `.txt` file. Off by default. |
| `filename_prefix` | STRING | Where to save and how to start the name. Default `promptgen/text`. |
| `filename` (optional) | STRING | A name to use, for example the `name` output of **PromptGen Counter**. |

| Output | Type | Description |
|---|---|---|
| `text` | STRING | The same text, passed through. |

How the file name is made:
- **Without `filename`:** `filename_prefix` plus the next free number. `promptgen/text` saves as `output/promptgen/text_00001.txt`, then `text_00002.txt`, and so on.
- **With `filename`:** the parts are put together in this order: the folder from `filename` (outermost), then the folder from `filename_prefix`, then the prefix's name part and the file name joined with `_`, then `.txt`. A prefix ending in `/` is a folder only.

  | `filename` (e.g. from the Counter) | `filename_prefix` | Saved as (inside `output/`) |
  |---|---|---|
  | `ArtemyFantasy/prompt_0001` | `before/` | `ArtemyFantasy/before/prompt_0001.txt` |
  | `ArtemyFantasy/prompt_0001` | `before/rewrite` | `ArtemyFantasy/before/rewrite_prompt_0001.txt` |
  | `prompt_0001` | `promptgen/before` | `promptgen/before_prompt_0001.txt` |
  | `prompt_0001` | `promptgen/` | `promptgen/prompt_0001.txt` |

  So a Counter prefix like `ArtemyFantasy/prompt` puts a whole run in its own project folder, and each save node picks its subfolder inside it.
- Repeated separators such as `__`, `--` or `_-` become a single one, and separators at the start or end of a name are removed.
- Existing files are never overwritten. If a name is taken, `_2`, `_3`, ... is added.
- Paths outside the `output` folder are refused.

Using two save nodes with different prefixes, for example `before/` and `after/`, lets one Counter name both the original prompt and the rewritten prompt without the files clashing.

### PromptGen Counter

Gives every run its own number, for numbered file names.

| Input | Type | Description |
|---|---|---|
| `prefix` | STRING | Text in front of the number. Default `prompt`. |
| `digits` | INT | How many digits the number is padded to: `4` gives `0001`. Default 4. |
| `current_number` | INT | The number to use next. Type a number to jump to it. |
| `auto_increment` | BOOLEAN | On (the default): the number goes up by 1 on every run, also when you queue a batch of runs at once. Off: the same number every run. |

| Output | Type | Description |
|---|---|---|
| `number` | INT | The number for this run. |
| `name` | STRING | `prefix_` plus the padded number, for example `prompt_0001`. Connect it to a save node's `filename` input. |

Notes:
- The count is kept in the workflow (the `current_number` field) and in memory, never in a file. After you restart ComfyUI, counting continues from the number shown in the field.
- Queueing a batch of 5 gives 1, 2, 3, 4, 5.

### PromptGen Batch Text Loader

Loads one `.txt` file from a folder on each run, so you can make one image per saved prompt.

| Input | Type | Description |
|---|---|---|
| `folder` | STRING | A full path such as `C:\prompts`, or a folder inside ComfyUI's `output` folder such as `promptgen/after`. Default `promptgen`. |
| `index` | INT | Which file to load. `0` is the first file. Files are sorted by name. |
| `auto_increment` | BOOLEAN | On (the default): `index` goes up by 1 on every run, so each run loads the next file. Off: the same file every run. |
| `when_done` | list | What happens after the last file. **stop**: the run stops with a message saying all files are done. **start over**: it goes back to the first file. |

| Output | Type | Description |
|---|---|---|
| `text` | STRING | The contents of the file. |
| `name` | STRING | The file name without `.txt`, for example `prompt_0001`. Useful as the `filename` for the image or settings you save. |
| `index` | INT | The index of the file that was loaded. |
| `total` | INT | How many `.txt` files are in the folder. |

**Queue all files button:** counts the files left in the folder, from `index` to the end, and queues exactly that many runs. One click processes the whole folder.

Only `.txt` files directly in the folder are used, not files in subfolders.

### PromptGen Save Settings

Saves the settings of a run as a `.json` file and shows them on the node. Connect the positive and negative prompt yourself. The sampler settings, model and resolution are read from the running workflow, so you don't need to wire those in.

What it records:
- **Prompts:** whatever you connect to `positive_prompt` and `negative_prompt`. `null` when nothing is connected.
- **Samplers:** for every **KSampler** and **KSampler Advanced**, `seed` / `noise_seed`, `steps`, `cfg`, `sampler_name`, `scheduler` and `denoise`. The advanced sampler also records `add_noise`, `start_at_step`, `end_at_step` and `return_with_leftover_noise`. The seed is the one actually used in that run, even when the KSampler's seed is set to *randomize*.
- **Model:** from Load Checkpoint or Load Diffusion Model. A list when the workflow has more than one.
- **Resolution:** taken from the connected image if there is one, otherwise from the Empty Latent Image node.

| Input | Type | Description |
|---|---|---|
| `filename_prefix` | STRING | Works the same as in Show / Save Text. Default `promptgen/settings`. |
| `image` (optional) | IMAGE | Connect the decoded image, for example from VAE Decode. The node then runs after the image is made and records its real size. |
| `filename` (optional) | STRING | Works the same as in Show / Save Text, for example the `name` from the Counter or the Batch Text Loader. The file gets `.json` instead of `.txt`. |
| `positive_prompt` (optional) | STRING | The positive prompt, for example the Batch Text Loader's `text` or the Ollama Rewrite output. |
| `negative_prompt` (optional) | STRING | The negative prompt. |

| Output | Type | Description |
|---|---|---|
| `json` | STRING | The saved JSON text. |

Example file:
```json
{
  "positive_prompt": "A 2d european comicbook illustration of a cow standing on a water lily ...",
  "negative_prompt": "blurry, low quality",
  "model": "sdxl.safetensors",
  "resolution": { "width": 832, "height": 1216, "batch_size": 1, "source": "image" },
  "samplers": [
    { "node": "3", "type": "KSampler", "seed": 123456, "steps": 30, "cfg": 6.5,
      "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0 }
  ]
}
```

---|---|---|
| `filename_prefix` | STRING | Works the same as in Show / Save Text. Default `promptgen/settings`. |
| `image` (optional) | IMAGE | Connect the decoded image, for example from VAE Decode. The node then runs after the image is made and records its real size. |
| `filename` (optional) | STRING | Works the same as in Show / Save Text, for example the `name` from the Counter or the Batch Text Loader. |

| Output | Type | Description |
|---|---|---|
| `settings` | STRING | The saved settings text. |

Example output:
```
KSampler (node 3)
  seed: 123456
  steps: 30
  cfg: 6.5
  sampler_name: euler
  scheduler: normal
  denoise: 1.0
Model: sdxl.safetensors
Resolution: 832 x 1216 (batch 1)
```

---

## Example workflows

### 1. Generate a folder of prompts

```
Line List (subjects) ──► 1 ┐
Line List (places)   ──► 2 ┴► Template ──► Show / Save Text (prefix "promptgen/before/")
                                   │
                                   └──► Ollama Rewrite ──► Show / Save Text (prefix "promptgen/after/")
Counter (prefix "prompt") ── name ──► filename of both save nodes
```

1. Add two or more **Line List** nodes with your snippets and connect them to inputs `1`, `2`, ... of a **Template** node.
2. Write your template, for example `The {1} sat on the {2}`, and set the Template's seed control to *randomize*.
3. Optionally connect the Template's `prompt` to **Ollama Rewrite** and write your instruction.
4. Add a **Show / Save Text** node for each text you want to keep, with `save_to_file` on and a prefix such as `promptgen/before/` or `promptgen/after/`.
5. Add a **Counter** with `auto_increment` on and connect its `name` to each save node's `filename`.
6. Set the batch count (for example 50) and queue. You get `output/promptgen/after/prompt_0001.txt` to `prompt_0050.txt`.

### 2. Make an image from each saved prompt

```
Batch Text Loader (folder "promptgen/after") ── text ──► CLIP Text Encode ──► KSampler ──► VAE Decode ──► Save Image
                                    └──────── name ──► Save Settings (filename) ◄── image ──┘
```

1. Add a **Batch Text Loader**, set `folder` to the folder from workflow 1 (for example `promptgen/after`), and set `index` to 0.
2. Connect `text` to the `text` input of CLIP Text Encode (positive). Build the rest of your usual image workflow.
3. Optionally add **Save Settings**: connect VAE Decode's image to `image`, the loader's `name` to `filename` and its `text` to `positive_prompt`, so every image gets a matching settings `.json`.
4. Click **Queue all files** on the Batch Text Loader. One image is made for each prompt file.

---

## Troubleshooting

- **New nodes or fields don't show up:** fully restart ComfyUI (close the console window too) and refresh the browser with Ctrl+F5. After an update that changes a node's fields, delete the old node and add it again.
- **The counter doesn't go up:** check that `auto_increment` is on.
- **The Ollama model list is empty:** start Ollama, then press **R** in ComfyUI.
- **The rewrite contains the model's reasoning:** leave `thinking` off.

---

## Development

```
comfyui-promptgen/
  __init__.py              entry point ComfyUI loads (node list, web folder, routes)
  promptgen/
    __init__.py            node registry: node IDs and display names
    comfy.py               the only module that touches ComfyUI (output folder, logging)
    routes.py              /promptgen/count_files, used by the "Queue all files" button
    core/                  plain Python, no ComfyUI imports, fully tested
      templating.py        {1}, {2} ... filling
      filenames.py         name cleaning, prefix + filename, safe saving
      counting.py          shared auto-increment (in memory only)
      textfiles.py         finding and reading .txt files
      settings.py          collects prompts, samplers, model and resolution for the JSON
      ollama_client.py     Ollama HTTP client
    nodes/                 thin ComfyUI node classes
      text.py              Line List, Template, Show / Save Text
      counter.py           Counter, Batch Text Loader
      settings.py          Save Settings
      ollama.py            Ollama Rewrite
      common.py            shared node pieces
  js/                      frontend scripts (common.js holds shared helpers)
  tests/                   pytest tests
```

Run the tests (no ComfyUI needed):

```
pip install pytest
pytest
```

Node IDs (`PromptGenCounter`, ...) and input names are part of saved workflows. Don't rename them.

## License

MIT, see [LICENSE](LICENSE).
