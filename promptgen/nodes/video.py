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
        "container": (list(containers), {"default": containers[0]}),
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
                "video": ("VIDEO",),
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

class PromptGenVR180Stereo:
    DESCRIPTION = (
        "Turns a mono video plus depth into 180° side-by-side stereo (VR180, left|right). Each eye is rendered by "
        "looking up depth and sampling the source (no splatting, so no holes to fill). The source is treated as "
        "a normal camera with the given field of view, placed on a 180°x180° dome per eye; outside the frame is "
        "black. Depth can be DA3 geometry (best: Metric-Large) or a depth IMAGE. Connect 'stereo' to Save VR180 "
        "Video, which renders and encodes a few frames at a time."
    )
    CATEGORY = VIDEO_CATEGORY
    RETURN_TYPES = ("VR180_STEREO", "IMAGE", "STRING")
    RETURN_NAMES = ("stereo", "preview", "info")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        from ..core.vr180 import DEPTH_FORMATS, RESOLUTION_PRESETS, SENSOR_WIDTHS_MM

        return {
            "required": {
                "depth_format": (DEPTH_FORMATS, {
                    "default": "DA3 Metric-Large raw",
                    "tooltip": "What the depth values mean.\n"
                               "- metric depth (meters): already in metres.\n"
                               "- DA3 Metric-Large raw: da3_geometry (or Render 'raw') from the Metric-Large model; "
                               "converted with the FOV and da3_resolution.\n"
                               "- relative depth (far = bigger): e.g. DA3 Mono/Base raw; scaled so the median is "
                               "reference_depth_m.\n"
                               "- depth map, near = white: DA3 Render depth (v2_style/min_max); mapped to near_m..far_m.\n"
                               "- disparity map, near = white: Depth Anything V2, Video Depth Anything; "
                               "mapped to near_m..far_m."}),
                "resolution": (list(RESOLUTION_PRESETS), {"default": "5760x2880 (2880 per eye)",
                                                          "tooltip": "Side-by-side size. Each eye is square."}),
                "custom_eye_size": ("INT", {"default": 2880, "min": 256, "max": 4096, "step": 16,
                                            "tooltip": "Per eye size when resolution is 'custom'."}),
                "hfov_deg": ("FLOAT", {"default": 65.0, "min": 10.0, "max": 170.0, "step": 0.5,
                                       "tooltip": "Horizontal field of view of the camera that filmed the source."}),
                "focal_length_mm": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1000.0, "step": 0.5,
                                              "tooltip": "If > 0, used with sensor instead of hfov_deg."}),
                "sensor": (list(SENSOR_WIDTHS_MM), {"default": next(iter(SENSOR_WIDTHS_MM))}),
                "fov_scale": ("FLOAT", {"default": 1.0, "min": 0.25, "max": 2.5, "step": 0.01,
                                        "tooltip": "Fudge factor: >1 shows the picture bigger on the dome."}),
                "ipd_mm": ("FLOAT", {"default": 64.0, "min": 0.0, "max": 300.0, "step": 0.5,
                                     "tooltip": "Distance between the eyes. More = stronger 3D."}),
                "depth_scale": ("FLOAT", {"default": 1.0, "min": 0.05, "max": 20.0, "step": 0.05,
                                          "tooltip": "Multiplies all depths. >1 = world farther away = less 3D."}),
                "min_depth_m": ("FLOAT", {"default": 0.3, "min": 0.05, "max": 10.0, "step": 0.05,
                                          "tooltip": "Nothing is treated as closer than this (limits the shift)."}),
                "near_m": ("FLOAT", {"default": 0.5, "min": 0.05, "max": 100.0, "step": 0.05,
                                     "tooltip": "For the 'near = white' formats: depth of white."}),
                "far_m": ("FLOAT", {"default": 30.0, "min": 0.5, "max": 10000.0, "step": 0.5,
                                    "tooltip": "For the 'near = white' formats: depth of black."}),
                "reference_depth_m": ("FLOAT", {"default": 3.0, "min": 0.1, "max": 1000.0, "step": 0.1,
                                                "tooltip": "For 'relative depth': the median depth in metres."}),
                "da3_resolution": ("INT", {"default": 504, "min": 140, "max": 2520, "step": 14,
                                           "tooltip": "For 'DA3 Metric-Large raw': the resolution set on "
                                                      "Run Depth Anything 3."}),
                "iterations": ("INT", {"default": 3, "min": 1, "max": 8,
                                       "tooltip": "Depth lookups per pixel. 2-3 is plenty."}),
                "depth_blur_px": ("FLOAT", {"default": 2.0, "min": 0.0, "max": 50.0, "step": 0.5,
                                            "tooltip": "Softens depth edges (in source pixels). Less tearing, "
                                                       "slightly rounder edges."}),
                "temporal_smoothing": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 0.95, "step": 0.05,
                                                 "tooltip": "Averages depth over frames to reduce flicker."}),
                "chunk_size": ("INT", {"default": 2, "min": 1, "max": 64,
                                       "tooltip": "Frames rendered at once on the GPU. Lower if you run out "
                                                  "of VRAM."}),
                "preview_frame": ("INT", {"default": 0, "min": 0, "max": 0x7FFFFFFF}),
            },
            "optional": {
                "images": ("IMAGE", {"tooltip": "The source frames. If empty, the frames in da3_geometry."}),
                "da3_geometry": ("DA3_GEOMETRY", {"tooltip": "From Run Depth Anything 3 (uses raw depth and sky)."}),
                "depth": ("IMAGE", {"tooltip": "A depth IMAGE instead of da3_geometry."}),
            },
        }

    def run(self, depth_format, resolution, custom_eye_size, hfov_deg, focal_length_mm, sensor, fov_scale,
            ipd_mm, depth_scale, min_depth_m, near_m, far_m, reference_depth_m, da3_resolution, iterations,
            depth_blur_px, temporal_smoothing, chunk_size, preview_frame, images=None, da3_geometry=None,
            depth=None):
        from ..core import vr180

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
        settings = vr180.StereoSettings(hfov_deg=hfov_deg, focal_mm=focal_length_mm,
                                        sensor_width_mm=vr180.SENSOR_WIDTHS_MM.get(sensor, 36.0),
                                        fov_scale=fov_scale, ipd_mm=ipd_mm, iterations=iterations,
                                        depth_blur_px=depth_blur_px)
        settings.eye_size = vr180.eye_size_for(resolution, custom_eye_size, width, settings)
        factor = vr180.da3_metric_factor(width, height, settings.source_hfov_deg(), da3_resolution)
        inv = vr180.to_inverse_depth(raw.cpu(), depth_format, depth_scale=depth_scale, near_m=near_m, far_m=far_m,
                                     reference_m=reference_depth_m, min_depth_m=min_depth_m, da3_factor=factor,
                                     sky=sky.cpu() if sky is not None else None)
        inv = vr180.temporal_smooth(inv, temporal_smoothing)

        clip = vr180.StereoClip(frames, inv, settings, chunk_size, torch_device())
        i = min(preview_frame, len(clip) - 1)
        preview = clip.render(i, i + 1).cpu()

        info = self._info(clip, width, height, inv)
        log.info("VR180: %s", info.replace("\n", "; "))
        return {"ui": {"text": [info]}, "result": (clip, preview, info)}

    @staticmethod
    def _info(clip, width, height, inv) -> str:
        import math

        from ..core.vr180 import focal_px

        s = clip.settings
        f = focal_px(width, s.shown_hfov_deg())
        src_ppd = f * math.pi / 180
        out_ppd = s.eye_size / 180
        valid = inv[inv > 0]
        near = 1 / float(valid.max()) if valid.numel() else float("inf")
        median = 1 / float(valid.median()) if valid.numel() else float("inf")
        vfov = math.degrees(2 * math.atan((height / 2) / f))
        return (f"{len(clip)} frames, SBS {2 * s.eye_size}x{s.eye_size} ({s.eye_size} per eye)\n"
                f"Source {width}x{height} shown at {s.shown_hfov_deg():.1f}° x {vfov:.1f}°\n"
                f"Sharpness: source {src_ppd:.1f} px/deg, output {out_ppd:.1f} px/deg\n"
                f"Depth: nearest {near:.2f} m, median {median:.2f} m (median of the sample)")


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
                "stereo": ("VR180_STEREO",),
                "fps": ("FLOAT", {"default": 30.0, "min": 1.0, "max": 240.0, "step": 0.001,
                                  "tooltip": "Connect the fps output of the Batch Video Loader."}),
                "filename_prefix": ("STRING", {"default": "vr180/",
                                               "tooltip": "Folder and/or prefix inside the output folder."}),
                "add_180_LR_suffix": ("BOOLEAN", {"default": True}),
                "write_vr180_metadata": ("BOOLEAN", {"default": True,
                                                     "tooltip": "Spherical video V2 boxes (mp4/mov only)."}),
                **encoder_inputs(codec="h265 (libx265)", crf=18, preset="medium", containers=["mp4", "mov", "mkv"]),
            },
            "optional": {
                "audio": ("AUDIO",),
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
