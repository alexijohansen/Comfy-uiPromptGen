# comfyui-promptgen

Custom nodes for [ComfyUI](https://github.com/comfyanonymous/ComfyUI) that build random prompts from your own lists of text snippets. You can also have a local LLM rewrite the prompts through [Ollama](https://ollama.com), save the prompts and the generation settings as text files, and later load those files back in to make an image for each one. There are also video nodes: a batch video loader, a high quality Save Video, and nodes that turn mono videos into 180° 3D (VR180) videos using a depth map.

All nodes are in the **PromptGen** category of the node menu, the video nodes in **PromptGen/video**.

| Node | What it does |
|---|---|
| [PromptGen Line List](#promptgen-line-list) | A list of entries, one per line |
| [PromptGen Template](#promptgen-template) | Fills `{1}`, `{2}`, ... in a template with random lines from the lists |
| [PromptGen Ollama Rewrite](#promptgen-ollama-rewrite) | Lets an Ollama model rewrite a prompt using your instruction |
| [PromptGen Show / Save Text](#promptgen-show--save-text) | Shows text on the node and can save it as a `.txt` file |
| [PromptGen Counter](#promptgen-counter) | A number that goes up with every run, plus a padded name like `prompt_0001` |
| [PromptGen Batch Text Loader](#promptgen-batch-text-loader) | Loads the next `.txt` file from a folder on every run |
| [PromptGen Batch Image Loader](#promptgen-batch-image-loader) | Loads the next image from a folder on every run |
| [PromptGen Save Settings](#promptgen-save-settings) | Saves the prompts, KSampler settings, seed, model, LoRAs and resolution as a `.json` file |
| [PromptGen Batch Video Loader](#promptgen-batch-video-loader) | Loads the next video (frames, fps, audio) from a folder on every run |
| [PromptGen Depth to VR180 Stereo](#promptgen-depth-to-vr180-stereo) | Turns a mono video plus depth into 180° side-by-side stereo |
| [PromptGen Save VR180 Video](#promptgen-save-vr180-video) | Renders and saves the stereo video as `<name>_180_LR.mp4` with audio and VR180 metadata |
| [PromptGen Save Video (High Quality)](#promptgen-save-video-high-quality) | Save Video with H.264/H.265 quality settings, 10-bit, and high quality or lossless audio |

## Installation

1. Clone or copy this repository into `ComfyUI/custom_nodes/`:
   ```
   cd ComfyUI/custom_nodes
   git clone <this repository's URL> comfyui-promptgen
   ```
2. Restart ComfyUI and refresh the browser page.

You don't need any extra Python packages. The video nodes use PyTorch and PyAV, which come with ComfyUI. The Ollama node needs [Ollama](https://ollama.com) running, by default at `http://localhost:11434`, with at least one model pulled (for example `ollama pull llama3.1`).

None of the nodes keep their own state on disk. Counters live in the workflow and in memory. The only files written are the `.txt`, `.json` and video files you ask the save nodes to write, and they always go inside ComfyUI's `output` folder.

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

### PromptGen Batch Image Loader

Works like the Batch Text Loader, but for images. Each run loads the next image from a folder, for example to upscale, caption or img2img a whole folder.

| Input | Type | Description |
|---|---|---|
| `folder` | STRING | A full path such as `D:\renders`, or a folder inside ComfyUI's `output` folder such as `ArtemyFantasy/images`. Empty means the `output` folder itself. |
| `index` | INT | Which image to load. `0` is the first image. Images are sorted by name. |
| `auto_increment` | BOOLEAN | On (the default): `index` goes up by 1 on every run, so each run loads the next image. Off: the same image every run. |
| `when_done` | list | What happens after the last image. **stop**: the run stops with a message saying all images are done. **start over**: it goes back to the first image. |

| Output | Type | Description |
|---|---|---|
| `image` | IMAGE | The image, the same as Load Image gives (EXIF rotation applied). |
| `mask` | MASK | From the image's transparency, 1 where it is transparent. All zeros for images without transparency. |
| `name` | STRING | The file name without extension, for example `prompt_0001`. Useful as the `filename` for what you save. |
| `index` | INT | The index of the image that was loaded. |
| `total` | INT | How many images are in the folder. |

**Queue all images button:** counts the images left in the folder, from `index` to the end, and queues exactly that many runs.

Supported files: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.gif` (first frame), `.tif` and `.tiff`, directly in the folder (not in subfolders).

### PromptGen Save Settings

Saves the settings of a run as a `.json` file and shows them on the node. Connect the positive and negative prompt yourself. The sampler settings, models, LoRAs and resolution are read from the running workflow, so you don't need to wire those in.

What it records:
- **Prompts:** what you type in, or connect to, `positive_prompt` and `negative_prompt`. `null` when the box is empty.
- **Samplers:** for every **KSampler** and **KSampler Advanced**, `seed` / `noise_seed`, `steps`, `cfg`, `sampler_name`, `scheduler` and `denoise`. The advanced sampler also records `add_noise`, `start_at_step`, `end_at_step` and `return_with_leftover_noise`. The seed is the one actually used in that run, even when the KSampler's seed is set to *randomize*.
- **Model:** `model` is the name of the first model loader (Load Checkpoint, Load Diffusion Model / UNET, GGUF loaders and other nodes with a `ckpt_name`, `unet_name` or `model_name` input). `models` lists every loader with its node id and type.
- **LoRAs:** `loras` lists every LoRA in the workflow with its name and strengths: `strength_model` and `strength_clip` for Load LoRA, `strength_model` for LoraLoaderModelOnly, and `strength` for multi-LoRA nodes such as rgthree's Power Lora Loader (only LoRAs that are switched on). It's an empty list when there are none.
- **Resolution:** taken from the connected image if there is one, otherwise from the Empty Latent Image node.

| Input | Type | Description |
|---|---|---|
| `filename_prefix` | STRING | Works the same as in Show / Save Text. Default `promptgen/settings`. |
| `image` (optional) | IMAGE | Connect the decoded image, for example from VAE Decode. The node then runs after the image is made and records its real size. |
| `filename` (optional) | STRING | Works the same as in Show / Save Text, for example the `name` from the Counter or the Batch Text Loader. The file gets `.json` instead of `.txt`. |
| `positive_prompt` (optional) | STRING | The positive prompt. Type it in the box, or connect any text output to it, for example the Batch Text Loader's `text`. |
| `negative_prompt` (optional) | STRING | The negative prompt. Type it in the box or connect a text output. |

| Output | Type | Description |
|---|---|---|
| `json` | STRING | The saved JSON text. |

Example file:
```json
{
  "positive_prompt": "A 2d european comicbook illustration of a cow standing on a water lily ...",
  "negative_prompt": "blurry, low quality",
  "model": "sdxl.safetensors",
  "models": [ { "node": "4", "type": "CheckpointLoaderSimple", "name": "sdxl.safetensors" } ],
  "loras": [
    { "node": "10", "type": "LoraLoader", "name": "comic_style.safetensors",
      "strength_model": 0.8, "strength_clip": 0.6 }
  ],
  "resolution": { "width": 832, "height": 1216, "batch_size": 1, "source": "image" },
  "samplers": [
    { "node": "3", "type": "KSampler", "seed": 123456, "steps": 30, "cfg": 6.5,
      "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0 }
  ]
}
```


### PromptGen Batch Video Loader

Works like the Batch Image Loader, but for videos. Each run loads the next video from a folder: all its frames, its frame rate and its audio. Made for the VR180 workflow, but it works for anything that takes frames. It is in the **PromptGen/video** category, like the other video nodes.

| Input | Type | Description |
|---|---|---|
| `folder` | STRING | A full path such as `D:\videos\mono`, or a folder inside ComfyUI's `output` folder. Empty means the `output` folder itself. |
| `index` | INT | Which video to load. `0` is the first. Videos are sorted by name. |
| `auto_increment` | BOOLEAN | On (the default): `index` goes up by 1 on every run. Off: the same video every run. |
| `when_done` | list | **stop** or **start over** after the last video, as in the other batch loaders. |
| `start_frame` | INT | Skip this many frames at the start. Default 0. |
| `max_frames` | INT | Load at most this many frames. `0` (the default) loads the whole video. |

| Output | Type | Description |
|---|---|---|
| `frames` | IMAGE | All loaded frames as one image batch. |
| `fps` | FLOAT | The video's frame rate, for example `29.97`. Connect it to the save node so the result plays at the same speed. |
| `audio` | AUDIO | The audio for the loaded frames (cut to match `start_frame` / `max_frames`). Empty when the video has no sound. |
| `name` | STRING | The file name without extension, for example `holiday_01`. Connect it to the save node's `name` / `filename`. |
| `index` | INT | The index of the video that was loaded. |
| `total` | INT | How many videos are in the folder. |

**Queue all videos button:** counts the videos left in the folder and queues exactly that many runs.

Supported files: `.mp4`, `.mov`, `.mkv`, `.webm`, `.avi` and `.m4v`, directly in the folder.

**Memory:** ComfyUI keeps frames as float images, so every frame of a 1280 pixel tall 16:9 video takes about 35 MB of RAM (plus about 12 MB for its depth map). A 20 second clip at 30 fps is about 600 frames, or roughly 28 GB. For longer videos, set `max_frames` (and `start_frame`) to do the video in parts.

### PromptGen Depth to VR180 Stereo

Turns a mono video plus a depth map into 180° side-by-side stereo, left eye on the left (VR180 LR). Connect its `stereo` output to **Save VR180 Video**.

How it works: the source is treated as a normal (pinhole) camera with the field of view you set, and is placed on a 180° x 180° dome for each eye, so things keep their real size in the headset. Everything outside the source frame is black. For every pixel of each eye, the node walks along that eye's line of sight, from near to far, and stops at the first point where the depth map says there's a surface (the shift for a point is about IPD/2 divided by its distance). It then reads the colour from the source at that spot. Because every output pixel reads from the source, there are never holes to fill. At the edges of near objects the background stretches a little instead. Nothing is generated or inpainted.

The node only prepares the clip and renders one preview frame. The Save node renders the frames a few at a time on the GPU and streams them straight into the video file, because a full 7680x3840 frame takes 350 MB as an image and a whole clip would not fit in memory.

| Input | Type | Description |
|---|---|---|
| `images` (optional) | IMAGE | The source frames, for example from the Batch Video Loader. If not connected, the frames stored in `da3_geometry` are used. |
| `da3_geometry` (optional) | DA3_GEOMETRY | From ComfyUI's **Run Depth Anything 3** node. The best option: the node uses the raw depth and also the sky mask (sky is set to infinitely far). |
| `depth` (optional) | IMAGE | A depth image instead, for example from **Render Depth Anything 3**, Depth Anything V2 or Video Depth Anything. Its size may differ from the frames. |
| `depth_format` | list | What the depth values mean. See the table below. Default `DA3 Metric-Large raw`. |
| `resolution` | list | Side-by-side output size, from `2880x1440` up to `8192x4096`. Each eye is square. **match source sharpness** picks the size that keeps the source's pixels per degree (capped at 4096 per eye). **custom** uses `custom_eye_size`. Default `5760x2880`. |
| `custom_eye_size` | INT | Per eye size for **custom**. Rounded to a multiple of 16. |
| `hfov_deg` | FLOAT | Horizontal field of view of the camera that filmed the source. Default 65°, about a 28 mm lens on full frame. Phones' main cameras are about 65-75°. |
| `focal_length_mm` | FLOAT | If above 0, used together with `sensor` instead of `hfov_deg`. Use the 35 mm equivalent focal length with the full frame sensor if that's what you know. |
| `sensor` | list | Sensor width for `focal_length_mm`. |
| `fov_scale` | FLOAT | Fudge factor for the size on the dome: above 1 shows the picture bigger (wider), below 1 smaller. Default 1. |
| `ipd_mm` | FLOAT | Distance between the eyes. Default 64 mm. More gives a stronger 3D effect (the world looks smaller). |
| `depth_scale` | FLOAT | Multiplies all depths. Above 1 pushes everything away (less 3D), below 1 brings it closer. Default 1. |
| `min_depth_m` | FLOAT | Nothing is treated as closer than this. Limits the biggest shift. Default 0.3 m. |
| `near_m`, `far_m` | FLOAT | Only for the two `near = white` formats. Those images have no units (every frame is stretched to black..white), so you say what distance white and black stand for. The metric formats take near and far from the depth data itself. Defaults 0.5 m and 30 m. |
| `reference_depth_m` | FLOAT | Only for `relative depth`: the clip's median depth is set to this. Default 3 m. |
| `da3_resolution` | INT | Only for `DA3 Metric-Large raw`: the `resolution` set on Run Depth Anything 3 (default 504). Needed to turn the raw values into metres. |
| `iterations` | INT | Only for method **fixed point**: depth lookups per pixel. Default 3. |
| `depth_blur_px` | FLOAT | Softens the depth map (in source pixels) before use. A little blur gives smoother edges. Default 2. |
| `temporal_smoothing` | FLOAT | Averages the depth over frames to reduce flicker. 0 (off) to 0.95. Default 0. |
| `chunk_size` | INT | Frames rendered at once on the GPU. Each 2880 px eye pair needs roughly 1 GB of VRAM. Lower it if you run out. Default 2. |
| `preview_frame` | INT | Which frame to show on the `preview` and `debug` outputs. |
| `method` | list | How each eye finds the depth to use. **ray march** (the default) steps along the eye's ray and takes the nearest surface it hits, so edges stay clean. **fixed point** is the original 3-lookup method: faster, but it can flip between the foreground and background depth next to depth edges, which shows as echoes or contour lines beside outlines. |
| `depth_dilate_px` | FLOAT | Grows near objects in the depth map by this many source pixels. Depth models often put the edge of hair or an outline on the background's depth, so those pixels stay behind as a halo. 2-4 usually fixes that. Default 0. |
| `strength` | FLOAT | Multiplies the 3D effect (the shift between the eyes). 0 is flat, 1 is real scale. The same as scaling `ipd_mm`. Default 1. |
| `near_outlier_percent` | FLOAT | Ignores the nearest this-many percent of the clip's depth when limiting how near things can be, so a few bad depth pixels can't cause big shifts. One limit for the whole clip, so it doesn't change from frame to frame. Default 0.5. |
| `debug_view` | list | What the `debug` output shows, see [Finding artifacts](#finding-artifacts). |

| Output | Type | Description |
|---|---|---|
| `stereo` | VR180_STEREO | The clip to render. Connect to Save VR180 Video. |
| `preview` | IMAGE | One rendered side-by-side frame at full output size. Connect a Preview Image node to check the settings before rendering a whole clip. |
| `info` | STRING | Output size, the source's angular size, its sharpness in pixels per degree, the nearest and median depth, and the largest shift. Also shown on the node. |
| `debug` | IMAGE | One eye-sized picture of `preview_frame`, chosen with `debug_view`. |

| `depth_format` | Use it for | How it is turned into metres |
|---|---|---|
| `metric depth (meters)` | Depth already in metres: Video Depth Anything metric models, Depth Anything V2 metric, or Render Depth Anything 3 with `raw` from a model whose raw output is metres | used as is |
| `DA3 Metric-Large raw` | `da3_geometry` (or Render Depth Anything 3 `raw`) from **Depth Anything 3 Metric-Large** | metres = raw x focal / 300, with the focal length in pixels at `da3_resolution` (the formula from the Depth Anything 3 authors) |
| `relative depth (far = bigger)` | `da3_geometry` from DA3 Small, Base or Mono-Large | scaled so the clip's median depth is `reference_depth_m` |
| `depth map, near = white` | Render Depth Anything 3 with `v2_style` or `min_max` | white = `near_m`, black = `far_m`, linear in between |
| `disparity map, near = white` | Depth Anything V2 (relative), Video Depth Anything (relative), MiDaS-style maps | white = `near_m`, black = `far_m`, linear in 1/distance |

### PromptGen Save VR180 Video

Renders the stereo clip and saves it as a side-by-side video with the audio. The frames are rendered on the GPU a few at a time and streamed into the encoder, so memory use stays low even at 8K. A progress bar shows on the node and **Cancel** stops it (the unfinished file is deleted).

The file is named `<prefix><name>_180_LR.mp4`, for example `output/vr180/holiday_01_180_LR.mp4`. DeoVR, Skybox and HereSphere detect 180° side-by-side from the `_180_LR` in the name. The node also writes the VR180 metadata (Spherical Video V2 `st3d`/`sv3d`) into MP4 and MOV files, which YouTube and ffmpeg-based players read. Existing files are never overwritten: a second `holiday_01` becomes `holiday_01_2_180_LR.mp4`.

| Input | Type | Description |
|---|---|---|
| `stereo` | VR180_STEREO | From Depth to VR180 Stereo. |
| `fps` | FLOAT | Frame rate. Connect the Batch Video Loader's `fps`. |
| `filename_prefix` | STRING | Folder and/or prefix inside the `output` folder, combined with `name` like the text save nodes do. Default `vr180/`. Without a `name` the files are numbered: `vr180/vr180_00001_180_LR.mp4`. |
| `add_180_LR_suffix` | BOOLEAN | Add `_180_LR` to the file name. Default on. |
| `write_vr180_metadata` | BOOLEAN | Write the VR180 metadata (MP4/MOV). For MKV the stereo mode is written instead. Default on. |
| `container`, `codec`, `crf`, `preset`, `pixel_format`, `audio_codec`, `audio_bitrate_kbps` | | The encoder settings, the same as in [Save Video (High Quality)](#promptgen-save-video-high-quality). Defaults: MP4, H.265 (libx265), CRF 18, preset medium, yuv420p, AAC 320 kbps. |
| `audio` (optional) | AUDIO | Connect the Batch Video Loader's `audio`. |
| `name` (optional) | STRING | Connect the Batch Video Loader's `name`. |

| Output | Type | Description |
|---|---|---|
| `path` | STRING | Full path of the saved video. |

**Which codec:** use H.265. Headsets decode it in hardware up to 8192 px wide, and H.264 files that big often stutter or don't play. `h265 (libx265)` runs on the CPU and is slow at these sizes (often 1-3 frames per second). On an NVIDIA card, `h265 NVIDIA (hevc_nvenc)` is many times faster at a slightly bigger file. `h264 NVIDIA` can't go above 4096 px wide, so it only works with the 2880x1440 and 3840x1920 presets.

### PromptGen Save Video (High Quality)

A replacement for ComfyUI's Save Video with all the quality settings. It takes the `VIDEO` from ComfyUI's **Create Video** (or Load Video) node. Frames are encoded 8 at a time, so it doesn't need extra memory, and it uses the PyAV / FFmpeg that comes with ComfyUI, so there's nothing else to install.

| Input | Type | Description |
|---|---|---|
| `video` | VIDEO | From Create Video. Leave Create Video's `codec` on **none**, so the frames reach this node without being compressed first. |
| `filename_prefix` | STRING | Folder and/or prefix inside the `output` folder. Default `video/ComfyUI`, which gives `output/video/ComfyUI_00001.mp4`. |
| `container` | list | `mp4` (plays everywhere), `mkv` or `mov`. |
| `codec` | list | `h264 (libx264)` (default), `h265 (libx265)`, or the NVIDIA encoders `h264_nvenc` / `hevc_nvenc` (much faster, need an NVIDIA card). |
| `crf` | INT | Quality: lower is better and bigger. **0 is lossless.** 12-18 looks the same as the original, 23 is what most tools use. Default 16. For NVIDIA this is the `cq` value (0 = lossless mode). |
| `preset` | list | Slower makes a smaller file at the same quality. Default `slow`. |
| `pixel_format` | list | `yuv420p` (default) plays everywhere. `yuv420p10le` is 10-bit: less banding in skies and gradients, plays on most modern players. `yuv444p` / `yuv444p10le` keep full colour detail, but many players (and browsers) can't play them. |
| `audio_codec` | list | `aac` (default, plays everywhere), `alac (lossless)`, `flac (lossless)`, `pcm 16-bit` / `pcm 24-bit (uncompressed)` (mkv or mov only) or `opus`. |
| `audio_bitrate_kbps` | INT | For AAC and Opus, 64-512. Default 320, which is very high quality. |
| `filename` (optional) | STRING | A name for the file, for example the Batch Video Loader's `name`. Combined with the prefix like the text save nodes do. Without it the files are numbered. |

The saved video is shown on the node. Colours are converted with the BT.709 matrix and tagged as such, so they look the same in every player (ComfyUI's own frames are sRGB).

Good settings:
- **Highest quality that still plays everywhere:** mp4, h264, CRF 12-16, preset slow, yuv420p, AAC 320.
- **Archive / lossless:** mkv, h264 or h265, CRF 0, yuv444p, flac.

---

## Making VR180 videos from mono videos

The VR180 nodes turn ordinary (mono) videos into 180° 3D side-by-side videos for VR headsets. They need a depth map for every frame. Use ComfyUI's built-in **Depth Anything 3** nodes for that (recommended), or another depth node.

### Set up Depth Anything 3

Recent versions of ComfyUI have Depth Anything 3 nodes built in (**Load Depth Anything 3**, **Run Depth Anything 3** and **Render Depth Anything 3**, in the *image/geometry estimation* category). If you can't find them, update ComfyUI (for the Windows portable version, run `update\update_comfyui.bat`) and restart.

1. Download a model from [Comfy-Org/Depth-Anything-3 on Hugging Face](https://huggingface.co/Comfy-Org/Depth-Anything-3/tree/main/geometry_estimation). For VR180, use **Metric-Large**, because it gives depth in metres, which is what makes the 3D look the right size:
   - [`depth_anything_3_metric_large.safetensors`](https://huggingface.co/Comfy-Org/Depth-Anything-3/blob/main/geometry_estimation/depth_anything_3_metric_large.safetensors) (recommended)
   - [`depth_anything_3_mono_large.safetensors`](https://huggingface.co/Comfy-Org/Depth-Anything-3/blob/main/geometry_estimation/depth_anything_3_mono_large.safetensors) (relative depth, also has a sky mask)
   - `depth_anything_3_base.safetensors` and `depth_anything_3_small.safetensors` (smaller and faster, relative depth)
2. Put it in `ComfyUI/models/geometry_estimation/`. For the Windows portable version: `C:\ComfyUI_windows_portable\ComfyUI\models\geometry_estimation\`. Create the folder if it doesn't exist.
3. Restart ComfyUI, or press **R** in the browser to refresh the model lists.

More about the models in [ComfyUI's Depth Anything 3 tutorial](https://docs.comfy.org/tutorials/utility/depth-anything-3) and the [Depth Anything 3 project](https://github.com/ByteDance-Seed/Depth-Anything-3).

On **Run Depth Anything 3**, leave `mode` on **mono**. `resolution` (default 504) is the size the model works at. Higher gives more detail in the depth but is slower. If you change it, set the same value as `da3_resolution` on the stereo node. Depth Anything 3 looks at each frame on its own, so the depth can flicker a little. If it bothers you, raise `temporal_smoothing` on the stereo node a bit (0.3-0.6), or use a Video Depth Anything custom node (search for it in ComfyUI Manager), which is made for video, with `depth_format` set to `disparity map, near = white`.

### Steps

Load the example workflow [`workflows/mono_to_vr180_sbs.json`](workflows/mono_to_vr180_sbs.json) (drag it onto ComfyUI), or build it:

```
Batch Video Loader ── frames ──► Run Depth Anything 3 ◄── Load Depth Anything 3 (Metric-Large)
     │  │  │  │                          │
     │  │  │  └── frames ──────────┐     └── da3_geometry ──┐
     │  │  │                       ▼                        ▼
     │  │  │                  Depth to VR180 Stereo ◄───────┘ ── preview ──► Preview Image
     │  │  │                       │
     │  │  │                     stereo
     │  │  │                       ▼
     │  │  └──── fps ─────► Save VR180 Video  ──► output/vr180/<name>_180_LR.mp4
     │  └─────── audio ───►        ▲
     └────────── name ────────────┘
```

1. Set the loader's `folder` to your folder of mono videos and `index` to 0.
2. On **Depth to VR180 Stereo**, set `hfov_deg` to your camera's field of view (or set `focal_length_mm` and `sensor`). If you don't know it, 65° is a good start for phone and action-camera-like footage. Leave `depth_format` on `DA3 Metric-Large raw` when you use the Metric-Large model.
3. Pick an output `resolution`. A 1280 pixel tall 16:9 video at 65° has about 31 pixels per degree, more than even the 7680x3840 preset (21), which the info text on the node shows, so a big preset such as `5760x2880` or `7680x3840` is worth it: each eye is rendered fresh, so more output pixels means sharper eyes, not upscaling blur.
4. For a quick test, set the loader's `max_frames` to about 30 and queue once. Look at the **preview** (left eye on the left) and the info text on the stereo node. Watch the test clip in your headset.
5. Adjust if needed: things look too big or too small, change `fov_scale`. The 3D is too strong or too weak, change `strength`. For artifacts, see [Finding artifacts](#finding-artifacts).
6. Set `max_frames` back to 0 and click **Queue all videos** on the loader. Every video in the folder becomes a `<name>_180_LR.mp4` in `output/vr180/`.


### Finding artifacts

Set the loader's `max_frames` to a few frames, pick a `preview_frame` that shows the problem, connect a Preview Image to the stereo node's `debug` output (the example workflow has one), and try the `debug_view`s:

| `debug_view` | What to look for |
|---|---|
| `anaglyph (red/cyan)` | Both eyes in one picture (red = left, cyan = right). With red/cyan glasses you can check the 3D on the monitor. Without them: far things should line up, near things should have colour fringes that get wider the nearer they are. |
| `left eye`, `right eye` | One eye at full size. Easier to zoom into than the side-by-side preview. |
| `no stereo (projection only)` | Both eyes with no shift. If something looks wrong here, it's the field of view (`hfov_deg`, `fov_scale`), not the depth. |
| `depth (near = white)` | The depth as the node uses it, after scaling, sky removal, dilation and blur. Check that it's smooth, that the edges sit on the edges of things in the picture, and that the sky is black. Noise or holes here show up as wobble in the result. |
| `shift map` | How far each pixel is shifted: blue is none, red the most. One very red spot means a few depth pixels are much too near: raise `near_outlier_percent` or `min_depth_m`. |
| `left minus right` | Where the eyes differ. Should look like outlines around near objects, fading out with distance. Repeated outlines next to each other are echoes: use method **ray march**. |

Common fixes:
- **Echoes or contour lines next to outlines:** use method **ray march** (the default since this update).
- **A halo of the foreground (hair, edges) left on the background:** raise `depth_dilate_px` to 2-4. If the depth edges are blurry in the `depth` view, also raise the `resolution` on Run Depth Anything 3 (for example 1008) and set the same `da3_resolution`.
- **Background smeared sideways next to near objects:** that's the stretching this method uses instead of hole filling. Lower `strength` or raise `depth_scale` to make it narrower.
- **Everything feels too strong or too weak:** change `strength`. Check the nearest and median depth in the info text: if they don't look like real distances, the depth format or `da3_resolution` is wrong.
- **Wobble or flicker between frames:** raise `temporal_smoothing`, or use a video depth model.

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

### 3. Turn a folder of mono videos into VR180 videos

[`workflows/mono_to_vr180_sbs.json`](workflows/mono_to_vr180_sbs.json). See [Making VR180 videos from mono videos](#making-vr180-videos-from-mono-videos).

### 4. Save a video at high quality

[`workflows/save_video_high_quality.json`](workflows/save_video_high_quality.json)

```
Batch Video Loader ── frames, fps, audio ──► Create Video (codec: none) ──► Save Video (High Quality)
         └──────────────── name ──────────────────────────────────────────► filename
```

Replace the loader with whatever makes your frames (for example a video model and VAE Decode). Keep Create Video's `codec` on **none**.

---

## Troubleshooting

- **New nodes or fields don't show up:** fully restart ComfyUI (close the console window too) and refresh the browser with Ctrl+F5. After an update that changes a node's fields, delete the old node and add it again.
- **The counter doesn't go up:** check that `auto_increment` is on.
- **The Ollama model list is empty:** start Ollama, then press **R** in ComfyUI.
- **The rewrite contains the model's reasoning:** leave `thinking` off.
- **Run Depth Anything 3 is missing or the model list is empty:** update ComfyUI, put the model in `models/geometry_estimation/` and press **R**. See [Set up Depth Anything 3](#set-up-depth-anything-3).
- **ComfyUI runs out of RAM on a long video:** set `max_frames` on the Batch Video Loader (see Memory under [Batch Video Loader](#promptgen-batch-video-loader)).
- **CUDA out of memory while saving a VR180 video:** lower `chunk_size` on the stereo node to 1, or pick a smaller resolution.
- **"Could not start the encoder":** the NVIDIA encoders need an NVIDIA card with current drivers, and `h264_nvenc` can't go above 4096 px wide. Pick `h265 (libx265)` instead. For the audio, PCM only works in mkv or mov.
- **The headset shows the video flat or as two pictures:** check the file name ends in `_180_LR` (keep `add_180_LR_suffix` on), or choose "180° SBS" in the player.
- **The 3D looks too strong, too weak, or the wrong size:** see step 5 of [Making VR180 videos](#steps).

---

## Development

```
comfyui-promptgen/
  __init__.py              entry point ComfyUI loads (node list, web folder, routes)
  promptgen/
    __init__.py            node registry: node IDs and display names
    comfy.py               the only module that touches ComfyUI (output folder, logging, GPU, progress bar)
    routes.py              /promptgen/count_files, used by the "Queue all files" button
    core/                  plain Python (+ PyTorch/PyAV for video), no ComfyUI imports, fully tested
      templating.py        {1}, {2} ... filling
      filenames.py         name cleaning, prefix + filename, safe saving
      counting.py          shared auto-increment and batch stepping (in memory only)
      textfiles.py         finding files for the batch loaders, reading .txt files
      images.py            reading an image file into image + mask arrays
      video.py             reading/writing video with PyAV, encoder settings, VR180 MP4 metadata
      vr180.py             mono + depth -> VR180 side by side (PyTorch, backward sampling)
      settings.py          collects prompts, samplers, models, LoRAs and resolution for the JSON
      ollama_client.py     Ollama HTTP client
    nodes/                 thin ComfyUI node classes
      text.py              Line List, Template, Show / Save Text
      counter.py           Counter
      batch.py             Batch Text Loader, Batch Image Loader (shared base class)
      settings.py          Save Settings
      ollama.py            Ollama Rewrite
      video.py             Batch Video Loader, Depth to VR180 Stereo, Save VR180 Video, Save Video (HQ)
      common.py            shared node pieces
  js/                      frontend scripts (common.js holds shared helpers)
  workflows/               example workflows
  tests/                   pytest tests
```

Run the tests (no ComfyUI needed):

```
pip install pytest numpy pillow torch av
pytest
```

Node IDs (`PromptGenCounter`, ...) and input names are part of saved workflows. Don't rename them.

## License

MIT, see [LICENSE](LICENSE).
