"""Video nodes: Batch Video Loader, VR180 Stereo, Save VR180 Video and Save Video (High Quality)."""

from __future__ import annotations

import os

from ..comfy import CATEGORY, Progress, check_interrupted, log, output_dir, torch_device
from ..core.filenames import display_path, unique_file_path
from ..core.video import (AUDIO_CODECS, CONTAINERS, PIXEL_FORMATS, PRESETS, VIDEO_CODECS, VIDEO_EXTENSIONS,
                          EncoderSettings, VideoWriter, inject_vr180_metadata, read_video)
from .batch import BatchFolderNode

VIDEO_CATEGORY = f"{CATEGORY}/video"


# ---- Batch Video Loader ----------------------------------------------------------------------

class PromptGenBatchVideo(BatchFolderNode):
    DESCRIPTION = (
        "Loads one video (mp4, mov, mkv, webm, ...) from a folder (sorted by name, index 0 is the first). With "
        "auto_increment on, each run loads the next video. 'folder' is a full path or a folder inside ComfyUI's "
        "output folder. Outputs the frames, fps, audio and the file name without extension. Every frame is held "
        "in memory as a float image (about 35 MB per 1280p frame), so use max_frames for long videos."
    )
    EXTENSIONS = VIDEO_EXTENSIONS
    KIND = "videos"
    DEFAULT_FOLDER = ""
    CATEGORY = VIDEO_CATEGORY
    RETURN_TYPES = ("IMAGE", "FLOAT", "AUDIO", "STRING", "INT", "INT")
    RETURN_NAMES = ("frames", "fps", "audio", "name", "index", "total")
    OUTPUT_TOOLTIPS = ("All loaded frames.", "Frames per second; connect to the save node.",
                       "The sound for the loaded frames (empty if the video has none).",
                       "File name without extension; connect to the save node's name.",
                       "Index of the loaded video.", "Number of videos in the folder.")

    @classmethod
    def INPUT_TYPES(cls):
        types = super().INPUT_TYPES()
        types["required"]["start_frame"] = ("INT", {"default": 0, "min": 0, "max": 0x7FFFFFFF,
                                                    "tooltip": "Skip this many frames at the start."})
        types["required"]["max_frames"] = ("INT", {"default": 0, "min": 0, "max": 0x7FFFFFFF,
                                                   "tooltip": "Load at most this many frames. 0 = all."})
        return types

    def load(self, path, start_frame=0, max_frames=0):
        import torch

        video = read_video(path, start_frame, max_frames)
        first = video.frames[0]
        frames = torch.empty((len(video.frames), *first.shape), dtype=torch.float32)
        for i in range(len(video.frames)):
            frames[i] = torch.from_numpy(video.frames[i]).float().div_(255.0)
            video.frames[i] = None  # free as we go
        audio = None
        if video.audio is not None:
            audio = {"waveform": torch.from_numpy(video.audio)[None], "sample_rate": video.sample_rate}
        log.info("Loaded %d frames (%dx%d, %.3f fps) from %s", frames.shape[0], first.shape[1], first.shape[0],
                 video.fps, path)
        return frames, video.fps, audio


# ---- encoder settings shared by both save nodes ----------------------------------------------

def encoder_inputs(codec="h264 (libx264)", crf=16, preset="slow", containers=CONTAINERS) -> dict:
    return {
        "container": (list(containers), {"default": containers[0],
                                         "tooltip": "File type. mp4 plays everywhere. mkv and mov also take "
                                                    "uncompressed (pcm) audio."}),
        "codec": (list(VIDEO_CODECS), {"default": codec,
                                       "tooltip": "NVIDIA encoders are much faster at high resolutions."}),
        "crf": ("INT", {"default": crf, "min": 0, "max": 51,
                        "tooltip": "Quality: lower is better and bigger. 0 = lossless, 12-18 = visually lossless, "
                                   "23 = default of most tools. For NVIDIA this is the cq value."}),
        "preset": (PRESETS, {"default": preset, "tooltip": "Slower = smaller file at the same quality."}),
        "pixel_format": (PIXEL_FORMATS, {"default": "yuv420p",
                                         "tooltip": "yuv420p plays everywhere. 10-bit (p10le) has less banding. "
                                                    "4:4:4 keeps full colour detail but many players can't play it."}),
        "audio_codec": (list(AUDIO_CODECS), {"default": "aac",
                                             "tooltip": "aac plays everywhere. alac/flac are lossless. pcm needs "
                                                        "mkv or mov."}),
        "audio_bitrate_kbps": ("INT", {"default": 320, "min": 64, "max": 512, "step": 32,
                                       "tooltip": "For aac and opus. 320 is very high quality."}),
    }


def _settings(kw: dict) -> EncoderSettings:
    return EncoderSettings.from_widgets(kw["codec"], kw["crf"], kw["preset"], kw["pixel_format"],
                                        kw["audio_codec"], kw["audio_bitrate_kbps"], kw["container"])


def _audio_arrays(audio, frames: int, fps: float):
    """ComfyUI AUDIO -> ((channels, samples) numpy, sample_rate), cut to the video's length."""
    if not audio or audio.get("waveform") is None:
        return None, 0
    waveform, rate = audio["waveform"], int(audio["sample_rate"])
    if hasattr(waveform, "detach"):
        waveform = waveform.detach().float().cpu().numpy()
    if waveform.ndim == 3:
        waveform = waveform[0]
    return waveform[:, : int(round(frames / fps * rate))], rate


def _preview(path: str) -> dict:
    """UI entry that makes ComfyUI show the saved video on the node."""
    out = output_dir()
    rel = display_path(path, out).replace("\\", "/")
    subfolder, filename = os.path.split(rel)
    return {"images": [{"filename": filename, "subfolder": subfolder, "type": "output"}], "animated": (True,),
            "saved_file": [rel]}


# ---- Save Video (High Quality) ---------------------------------------------------------------

class PromptGenSaveVideoHQ:
    DESCRIPTION = (
        "Saves a VIDEO (from ComfyUI's Create Video or Load Video) with full control over quality: H.264/H.265 "
        "CRF and preset, 10-bit or 4:4:4 colour, and AAC up to 512 kbps or lossless ALAC/FLAC/PCM audio. "
        "Frames are encoded a few at a time, so large videos don't need extra memory."
    )
    CATEGORY = VIDEO_CATEGORY
    RETURN_TYPES = ()
    FUNCTION = "run"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video": ("VIDEO", {"tooltip": "From Create Video (with its codec on 'none') or Load Video."}),
                "filename_prefix": ("STRING", {"default": "video/ComfyUI",
                                               "tooltip": "Folder and/or prefix inside the output folder."}),
                **encoder_inputs(),
            },
            "optional": {"filename": ("STRING", {"forceInput": True,
                                                 "tooltip": "e.g. the name from a Batch Video Loader."})},
        }

    def run(self, video, filename_prefix, filename=None, **kw):
        settings = _settings(kw)
        components = video.get_components()
        frames, fps = components.images, float(components.frame_rate)
        audio, rate = _audio_arrays(components.audio, frames.shape[0], fps)
        height, width = frames.shape[1], frames.shape[2]
        path = unique_file_path(filename_prefix, filename, output_dir(), f".{settings.container}",
                                default_prefix="video/ComfyUI")
        progress, step = Progress(frames.shape[0]), 8
        with VideoWriter(path, width - width % 2, height - height % 2, fps, settings, audio, rate) as writer:
            for start in range(0, frames.shape[0], step):
                check_interrupted()
                chunk = frames[start:start + step, : height - height % 2, : width - width % 2]
                writer.write_float(chunk)
                progress.update(chunk.shape[0])
        log.info("Saved video to %s", path)
        return {"ui": _preview(path)}


# ---- VR180 Stereo ----------------------------------------------------------------------------

def _advanced_inputs() -> dict:
    """The rarely changed stereo settings, with their defaults (VR180 Advanced Settings node)."""
    from ..core.vr180 import METHODS, SENSOR_WIDTHS_MM

    return {
        "ipd_mm": ("FLOAT", {"default": 64.0, "min": 0.0, "max": 300.0, "step": 0.5,
                             "tooltip": "Distance between your eyes in mm. 64 is average. The 'strength' on the "
                                        "main node multiplies this."}),
        "depth_scale": ("FLOAT", {"default": 1.0, "min": 0.05, "max": 20.0, "step": 0.05,
                                  "tooltip": "Multiplies every distance. Above 1 pushes the whole scene away (less "
                                             "3D), below 1 brings it closer. Usually 'strength' is all you need."}),
        "focal_length_mm": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1000.0, "step": 0.5,
                                      "tooltip": "Lens focal length. If above 0 it is used with 'sensor' instead of "
                                                 "hfov_deg. 0 = use hfov_deg."}),
        "sensor": (list(SENSOR_WIDTHS_MM), {"default": next(iter(SENSOR_WIDTHS_MM)),
                                            "tooltip": "Camera sensor size, only used with focal_length_mm. Pick "
                                                       "'35 mm equivalent' for phone focal lengths like '26 mm'."}),
        "fov_scale": ("FLOAT", {"default": 1.0, "min": 0.25, "max": 2.5, "step": 0.01,
                                "tooltip": "Fudge factor for how big the picture looks in the headset. 1.1 = 10% "
                                           "bigger."}),
        "custom_eye_size": ("INT", {"default": 2880, "min": 256, "max": 4096, "step": 16,
                                    "tooltip": "Size of each eye in pixels when 'resolution' is set to custom."}),
        "min_depth_m": ("FLOAT", {"default": 0.3, "min": 0.05, "max": 10.0, "step": 0.05,
                                  "tooltip": "Nothing is treated as nearer than this (in metres). Stops very near "
                                             "pixels from being shifted far."}),
        "near_outlier_percent": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 20.0, "step": 0.1,
                                           "tooltip": "Ignores the nearest this-many percent of the clip's depth "
                                                      "when limiting the shift, so a few bad depth pixels can't "
                                                      "cause big jumps. 0 = off."}),
        "near_m": ("FLOAT", {"default": 0.5, "min": 0.05, "max": 100.0, "step": 0.05,
                             "tooltip": "Only for the grey 'near = white' depth images, which have no units: the "
                                        "distance white stands for."}),
        "far_m": ("FLOAT", {"default": 30.0, "min": 0.5, "max": 10000.0, "step": 0.5,
                            "tooltip": "Only for the grey 'near = white' depth images: the distance black stands "
                                       "for."}),
        "reference_depth_m": ("FLOAT", {"default": 3.0, "min": 0.1, "max": 1000.0, "step": 0.1,
                                        "tooltip": "Only for 'relative depth': the typical (median) distance in the "
                                                   "clip, in metres."}),
        "da3_resolution": ("INT", {"default": 504, "min": 140, "max": 2520, "step": 14,
                                   "tooltip": "Only for 'DA3 Metric-Large raw': must match the 'resolution' on Run "
                                              "Depth Anything 3, or the distances come out wrong."}),
        "depth_blur_px": ("FLOAT", {"default": 2.0, "min": 0.0, "max": 50.0, "step": 0.5,
                                    "tooltip": "Softens the depth map (in source pixels). A little gives smoother "
                                               "edges."}),
        "depth_dilate_px": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 20.0, "step": 1.0,
                                      "tooltip": "Grows near objects in the depth map. Try 2-4 if hair or outlines "
                                                 "leave a halo on the background."}),
        "temporal_smoothing": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 0.95, "step": 0.05,
                                         "tooltip": "Averages the depth over frames to reduce flicker. 0 = off, "
                                                    "0.3-0.6 = noticeable smoothing."}),
        "straight_edges": ("BOOLEAN", {"default": True,
                                       "tooltip": "Keep the picture's edges straight. Off: the edges dent and bulge "
                                                  "with the depth."}),
        "edge_feather_px": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 200.0, "step": 0.5,
                                      "tooltip": "Softens the picture's edge over this many source pixels."}),
        "method": (METHODS, {"default": METHODS[0],
                             "tooltip": "ray march: clean edges (recommended). fixed point: older and faster, but "
                                        "can leave echoes next to outlines."}),
        "iterations": ("INT", {"default": 3, "min": 1, "max": 8,
                               "tooltip": "Only for method 'fixed point': depth lookups per pixel."}),
        "chunk_size": ("INT", {"default": 2, "min": 1, "max": 64,
                               "tooltip": "Frames rendered at once on the GPU when saving. Lower it if you get "
                                          "'out of memory'."}),
    }


def advanced_defaults() -> dict:
    return {name: spec[1]["default"] for name, spec in _advanced_inputs().items()}


class PromptGenVR180Settings:
    DESCRIPTION = ("Settings for Depth to VR180 Stereo that you rarely need. Connect it to the stereo node's "
                   "'advanced' input. Without it the defaults shown here are used. Hover over a setting to see "
                   "what it does.")
    CATEGORY = VIDEO_CATEGORY
    RETURN_TYPES = ("VR180_SETTINGS",)
    RETURN_NAMES = ("advanced",)
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": _advanced_inputs()}

    def run(self, **settings):
        return (settings,)


def _main_inputs() -> dict:
    from ..core.vr180 import DEBUG_VIEWS, DEPTH_FORMATS, RESOLUTION_PRESETS

    return {
        "depth_format": (DEPTH_FORMATS, {
            "default": "DA3 Metric-Large raw",
            "tooltip": "What kind of depth you connect:\n"
                       "- DA3 Metric-Large raw: Run Depth Anything 3 with the Metric-Large model (recommended).\n"
                       "- metric depth (meters): any depth already in metres.\n"
                       "- relative depth (far = bigger): Run Depth Anything 3 with Small, Base or Mono-Large.\n"
                       "- depth map, near = white: the grey image from Render Depth Anything 3.\n"
                       "- disparity map, near = white: Depth Anything V2 or Video Depth Anything."}),
        "resolution": (list(RESOLUTION_PRESETS), {
            "default": "5760x2880 (2880 per eye)",
            "tooltip": "Size of the side-by-side video. Bigger is sharper in the headset but slower to render and "
                       "encode. 5760x2880 is a good balance."}),
        "hfov_deg": ("FLOAT", {"default": 65.0, "min": 10.0, "max": 170.0, "step": 0.5,
                               "tooltip": "How wide the original camera saw, in degrees (horizontal field of "
                                          "view). Sets how big things look in the headset. Phones are about 65-75."}),
        "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 5.0, "step": 0.05,
                               "tooltip": "How strong the 3D effect is. 1 = real life, 0 = flat, 2 = twice as "
                                          "strong."}),
        "window_distance_m": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1000.0, "step": 0.1,
                                        "tooltip": "How far away the picture's frame appears, like a window you look "
                                                   "through. 0 = infinitely far. Try 2 if things cut off by the edge "
                                                   "feel odd."}),
        "debug_view": (DEBUG_VIEWS, {"default": DEBUG_VIEWS[0],
                                     "tooltip": "What the 'debug' output shows, to look for problems. See 'Finding "
                                                "artifacts' in the README."}),
        "preview_frame": ("INT", {"default": 0, "min": 0, "max": 0x7FFFFFFF,
                                  "tooltip": "Which frame the 'preview' and 'debug' outputs show."}),
    }


_OPTIONAL_INPUTS = {
    "images": ("IMAGE", {"tooltip": "The video frames, e.g. 'frames' from the Batch Video Loader. Can be left "
                                    "empty when da3_geometry is connected."}),
    "da3_geometry": ("DA3_GEOMETRY", {"tooltip": "Depth from Run Depth Anything 3 (best)."}),
    "depth": ("IMAGE", {"tooltip": "A depth image instead of da3_geometry, e.g. from another depth node."}),
}


def _info(clip, width, height, inv) -> str:
    import math

    from ..core.vr180 import focal_px

    s = clip.settings
    f = focal_px(width, s.shown_hfov_deg())
    valid = inv[inv > 0]
    near = 1 / float(valid.max()) if valid.numel() else float("inf")
    median = 1 / float(valid.median()) if valid.numel() else float("inf")
    vfov = math.degrees(2 * math.atan((height / 2) / f))
    max_shift = math.degrees(math.atan(s.ipd_mm / 2000 * float(inv.max())))
    return (f"{len(clip)} frames, SBS {2 * s.eye_size}x{s.eye_size} ({s.eye_size} per eye), {s.method}\n"
            f"Source {width}x{height} shown at {s.shown_hfov_deg():.1f}° x {vfov:.1f}°\n"
            f"Sharpness: source {f * math.pi / 180:.1f} px/deg, output {s.eye_size / 180:.1f} px/deg\n"
            f"Depth: nearest {near:.2f} m, median {median:.2f} m\n"
            f"Largest shift per eye: {max_shift:.2f}° ({max_shift * f * math.pi / 180:.0f} source px)")


def build_stereo(depth_format, resolution, hfov_deg, strength, window_distance_m, debug_view, preview_frame,
                 advanced=None, images=None, da3_geometry=None, depth=None) -> dict:
    """Shared by both stereo nodes. advanced: dict of _advanced_inputs() values (missing = default)."""
    from ..core import vr180

    a = {**advanced_defaults(), **(advanced or {})}
    if images is None and da3_geometry is not None:
        images = da3_geometry.get("image")
    if images is None:
        raise ValueError("Connect images (or da3_geometry, which carries its frames).")
    if da3_geometry is not None:
        raw, sky = da3_geometry["depth"], da3_geometry.get("sky")
    elif depth is not None:
        raw, sky = depth[..., 0], None
    else:
        raise ValueError("Connect da3_geometry or a depth image.")
    if raw.shape[0] not in (1, images.shape[0]):
        raise ValueError(f"{images.shape[0]} frames but {raw.shape[0]} depth maps.")

    frames = images[..., :3]
    _, height, width, _ = frames.shape
    settings = vr180.StereoSettings(hfov_deg=hfov_deg, focal_mm=a["focal_length_mm"],
                                    sensor_width_mm=vr180.SENSOR_WIDTHS_MM.get(a["sensor"], 36.0),
                                    fov_scale=a["fov_scale"], ipd_mm=a["ipd_mm"] * strength,
                                    iterations=a["iterations"], depth_blur_px=a["depth_blur_px"],
                                    depth_dilate_px=a["depth_dilate_px"], method=a["method"],
                                    straight_edges=a["straight_edges"], window_m=window_distance_m,
                                    edge_feather_px=a["edge_feather_px"])
    settings.eye_size = vr180.eye_size_for(resolution, a["custom_eye_size"], width, settings)
    factor = vr180.da3_metric_factor(width, height, settings.source_hfov_deg(), a["da3_resolution"])
    inv = vr180.to_inverse_depth(raw.cpu(), depth_format, depth_scale=a["depth_scale"], near_m=a["near_m"],
                                 far_m=a["far_m"], reference_m=a["reference_depth_m"], min_depth_m=a["min_depth_m"],
                                 da3_factor=factor, sky=sky.cpu() if sky is not None else None)
    inv = vr180.temporal_smooth(inv, a["temporal_smoothing"])
    inv, _ = vr180.clamp_near_outliers(inv, a["near_outlier_percent"])

    clip = vr180.StereoClip(frames, inv, settings, a["chunk_size"], torch_device())
    i = min(preview_frame, len(clip) - 1)
    preview = clip.render(i, i + 1).cpu()
    debug = clip.render_debug(i, debug_view).cpu()
    info = _info(clip, width, height, inv)
    log.info("VR180: %s", info.replace("\n", "; "))
    return {"ui": {"text": [info]}, "result": (clip, preview, info, debug)}


_STEREO_OUTPUTS = dict(
    RETURN_TYPES=("VR180_STEREO", "IMAGE", "STRING", "IMAGE"),
    RETURN_NAMES=("stereo", "preview", "info", "debug"),
    OUTPUT_TOOLTIPS=("Connect to Save VR180 Video, which renders and saves the whole clip.",
                     "One side-by-side frame (left eye on the left) to check before saving.",
                     "Sizes, sharpness, depth range and largest shift. Also shown on the node.",
                     "The view picked in debug_view."),
)


class PromptGenVR180:
    DESCRIPTION = (
        "Turns a mono video plus depth into 180° side-by-side stereo (VR180, left|right). The source is shown "
        "as seen through a window on a 180° dome, at its real size; outside it is black. Connect 'stereo' to "
        "Save VR180 Video. Rarely needed settings are on the VR180 Advanced Settings node (optional). "
        "Hover over a setting to see what it does."
    )
    CATEGORY = VIDEO_CATEGORY
    FUNCTION = "run"
    RETURN_TYPES = _STEREO_OUTPUTS["RETURN_TYPES"]
    RETURN_NAMES = _STEREO_OUTPUTS["RETURN_NAMES"]
    OUTPUT_TOOLTIPS = _STEREO_OUTPUTS["OUTPUT_TOOLTIPS"]

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": _main_inputs(),
                "optional": {**_OPTIONAL_INPUTS,
                             "advanced": ("VR180_SETTINGS", {"tooltip": "Optional: a VR180 Advanced Settings "
                                                                        "node. Without it the defaults are used."})}}

    def run(self, **kw):
        return build_stereo(**kw)


class PromptGenVR180Stereo:
    """The first version, with every setting on the node. Kept so saved workflows still load."""

    DESCRIPTION = ("Old version of Depth to VR180 Stereo with every setting on the node. Still works; for new "
                   "workflows use Depth to VR180 Stereo (+ VR180 Advanced Settings).")
    DEPRECATED = True  # hidden from the node search
    CATEGORY = VIDEO_CATEGORY
    FUNCTION = "run"
    RETURN_TYPES = _STEREO_OUTPUTS["RETURN_TYPES"]
    RETURN_NAMES = _STEREO_OUTPUTS["RETURN_NAMES"]
    OUTPUT_TOOLTIPS = _STEREO_OUTPUTS["OUTPUT_TOOLTIPS"]

    # The order of these inputs is how saved workflows store their values: never reorder.
    _ORDER = ["depth_format", "resolution", "custom_eye_size", "hfov_deg", "focal_length_mm", "sensor", "fov_scale",
              "ipd_mm", "depth_scale", "min_depth_m", "near_m", "far_m", "reference_depth_m", "da3_resolution",
              "iterations", "depth_blur_px", "temporal_smoothing", "chunk_size", "preview_frame", "method",
              "depth_dilate_px", "strength", "near_outlier_percent", "straight_edges", "window_distance_m",
              "edge_feather_px", "debug_view"]

    @classmethod
    def INPUT_TYPES(cls):
        everything = {**_main_inputs(), **_advanced_inputs()}
        return {"required": {name: everything[name] for name in cls._ORDER}, "optional": dict(_OPTIONAL_INPUTS)}

    def run(self, depth_format, resolution, hfov_deg, strength, window_distance_m, debug_view, preview_frame,
            images=None, da3_geometry=None, depth=None, **advanced):
        return build_stereo(depth_format, resolution, hfov_deg, strength, window_distance_m, debug_view,
                            preview_frame, advanced, images, da3_geometry, depth)


# ---- Save VR180 Video ------------------------------------------------------------------------

class PromptGenSaveVR180:
    DESCRIPTION = (
        "Renders the VR180 stereo clip a few frames at a time on the GPU and encodes it straight to an MP4 "
        "(side by side, left|right), with the audio. The file name gets _180_LR so DeoVR, Skybox and HereSphere "
        "recognise it, and VR180 metadata (as YouTube expects) is written into the file."
    )
    CATEGORY = VIDEO_CATEGORY
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("path",)
    FUNCTION = "run"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "stereo": ("VR180_STEREO", {"tooltip": "From Depth to VR180 Stereo."}),
                "fps": ("FLOAT", {"default": 30.0, "min": 1.0, "max": 240.0, "step": 0.001,
                                  "tooltip": "Connect the fps output of the Batch Video Loader."}),
                "filename_prefix": ("STRING", {"default": "vr180/",
                                               "tooltip": "Folder and/or prefix inside the output folder."}),
                "add_180_LR_suffix": ("BOOLEAN", {"default": True,
                                                  "tooltip": "Add _180_LR to the file name, which is how DeoVR, "
                                                             "Skybox and HereSphere know it's 180° side by side."}),
                "write_vr180_metadata": ("BOOLEAN", {"default": True,
                                                     "tooltip": "Write VR180 info into the file, for YouTube and "
                                                                "players that read it (mp4/mov)."}),
                **encoder_inputs(codec="h265 (libx265)", crf=18, preset="medium", containers=["mp4", "mov", "mkv"]),
            },
            "optional": {
                "audio": ("AUDIO", {"tooltip": "The sound, e.g. 'audio' from the Batch Video Loader."}),
                "name": ("STRING", {"forceInput": True, "tooltip": "e.g. the name from a Batch Video Loader."}),
            },
        }

    def run(self, stereo, fps, filename_prefix, add_180_LR_suffix, write_vr180_metadata, audio=None, name=None,
            **kw):
        settings = _settings(kw)
        width, height = stereo.size
        audio_arr, rate = _audio_arrays(audio, len(stereo), fps)
        path = unique_file_path(filename_prefix, name, output_dir(), f".{settings.container}",
                                suffix="_180_LR" if add_180_LR_suffix else "", default_prefix="vr180/vr180")
        progress = Progress(len(stereo))
        stream_metadata = {"stereo_mode": "left_right"} if settings.container == "mkv" else None
        with VideoWriter(path, width, height, fps, settings, audio_arr, rate, stream_metadata) as writer:
            for chunk in stereo.chunks(high_bit_depth=settings.high_bit_depth):
                check_interrupted()
                writer.write(chunk)
                progress.update(chunk.shape[0])
        if write_vr180_metadata and settings.container in ("mp4", "mov") and not inject_vr180_metadata(path):
            log.warning("Could not add VR180 metadata to %s (the _180_LR name still works).", path)
        log.info("Saved VR180 video to %s", path)
        ui = _preview(path)
        return {"ui": ui, "result": (path,)}
