"""Reading and writing video files with PyAV (ComfyUI ships it), plus VR180 metadata for MP4.

Frames are uint8 numpy arrays here; the nodes turn them into ComfyUI IMAGE tensors.
Audio is float32 (channels, samples) in -1..1, like ComfyUI's AUDIO waveform without the batch.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from fractions import Fraction

import numpy as np

VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")

@dataclass
class VideoData:
    frames: list[np.ndarray]           # each (H, W, 3) uint8
    fps: float
    audio: np.ndarray | None           # (channels, samples) float32
    sample_rate: int


def read_video(path: str, start_frame: int = 0, max_frames: int = 0) -> VideoData:
    """Decode frames start_frame .. start_frame + max_frames - 1 (max_frames 0 = to the end),
    and the audio for the same stretch of time."""
    import av

    frames: list[np.ndarray] = []
    with av.open(path) as container:
        if not container.streams.video:
            raise ValueError(f"No video stream in {path}")
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        rate = stream.average_rate or stream.guessed_rate or stream.base_rate or 30
        fps = float(rate)
        for i, frame in enumerate(container.decode(stream)):
            if i < start_frame:
                continue
            if max_frames and len(frames) >= max_frames:
                break
            frames.append(frame.to_ndarray(format="rgb24"))
    if not frames:
        raise ValueError(f"No frames to load from {path} (start_frame {start_frame}).")

    audio, sample_rate = read_audio(path)
    if audio is not None:
        first = int(round(start_frame / fps * sample_rate))
        last = int(round((start_frame + len(frames)) / fps * sample_rate))
        audio = audio[:, first:last]
        if audio.shape[1] == 0:
            audio = None
    return VideoData(frames, fps, audio, sample_rate)


def read_audio(path: str) -> tuple[np.ndarray | None, int]:
    """((channels, samples) float32, sample_rate) of the first audio stream, or (None, 0)."""
    import av

    with av.open(path) as container:
        streams = [s for s in container.streams.audio if s.codec_context is not None]
        if not streams:
            return None, 0
        stream = streams[0]
        channels = min(stream.codec_context.channels or 2, 2)
        rate = stream.codec_context.sample_rate or stream.rate
        resampler = av.AudioResampler(format="fltp", layout="stereo" if channels == 2 else "mono", rate=rate)
        chunks = []
        try:
            for frame in container.decode(stream):
                for out in resampler.resample(frame):
                    chunks.append(out.to_ndarray())
            for out in resampler.resample(None):
                chunks.append(out.to_ndarray())
        except av.error.FFmpegError:
            if not chunks:
                return None, 0
    if not chunks:
        return None, 0
    return np.concatenate(chunks, axis=1).astype(np.float32), int(rate)


# ---- encoding ----------------------------------------------------------------------------

# name shown on the node -> PyAV encoder
VIDEO_CODECS = {
    "h264 (libx264)": "libx264",
    "h265 (libx265)": "libx265",
    "h264 NVIDIA (h264_nvenc)": "h264_nvenc",
    "h265 NVIDIA (hevc_nvenc)": "hevc_nvenc",
}
PRESETS = ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"]
PIXEL_FORMATS = ["yuv420p", "yuv420p10le", "yuv444p", "yuv444p10le"]
# name shown on the node -> (PyAV encoder, containers it can go in)
AUDIO_CODECS = {
    "aac": ("aac", ("mp4", "mov", "mkv")),
    "alac (lossless)": ("alac", ("mp4", "mov", "mkv")),
    "flac (lossless)": ("flac", ("mp4", "mkv")),
    "pcm 16-bit (uncompressed)": ("pcm_s16le", ("mov", "mkv")),
    "pcm 24-bit (uncompressed)": ("pcm_s24le", ("mov", "mkv")),
    "opus": ("libopus", ("mp4", "mkv")),
}
CONTAINERS = ["mp4", "mkv", "mov"]


@dataclass
class EncoderSettings:
    codec: str = "libx264"          # PyAV encoder name
    crf: int = 16                   # 0 = lossless (x264/x265), ~16-18 = visually lossless
    preset: str = "slow"
    pix_fmt: str = "yuv420p"
    audio_codec: str = "aac"        # PyAV encoder name
    audio_bitrate_kbps: int = 320   # aac / opus only
    container: str = "mp4"

    @classmethod
    def from_widgets(cls, codec: str, crf: int, preset: str, pix_fmt: str, audio_codec: str,
                     audio_bitrate_kbps: int, container: str = "mp4") -> "EncoderSettings":
        """From the names shown on the nodes. Raises ValueError for combinations that can't work."""
        video = VIDEO_CODECS.get(codec, codec)
        audio, allowed = AUDIO_CODECS.get(audio_codec, (audio_codec, tuple(CONTAINERS)))
        if container not in allowed:
            raise ValueError(f"Audio '{audio_codec}' can't go in .{container}. Use .{' or .'.join(allowed)}.")
        return cls(video, int(crf), preset, pix_fmt, audio, int(audio_bitrate_kbps), container)

    def video_options(self) -> dict:
        if self.codec.endswith("nvenc"):
            # NVENC has its own presets p1 (fastest) .. p7 (best); cq is its CRF-like quality.
            index = PRESETS.index(self.preset) if self.preset in PRESETS else 5
            options = {"preset": f"p{min(7, max(1, index - 1))}", "rc": "vbr", "cq": str(max(self.crf, 1)), "b": "0"}
            if self.crf == 0:
                options = {"preset": "p7", "tune": "lossless"}
            return options
        options = {"crf": str(self.crf), "preset": self.preset}
        if self.codec == "libx265":
            options["x265-params"] = "log-level=error" + (":lossless=1" if self.crf == 0 else "")
        return options

    @property
    def high_bit_depth(self) -> bool:
        return "10" in self.pix_fmt


def _set_bt709(codec_context) -> None:
    """Tag the stream as BT.709 limited range (the matrix the frames are converted with)."""
    for name, value in (("color_primaries", 1), ("color_trc", 1), ("colorspace", 1), ("color_range", 1)):
        try:
            setattr(codec_context, name, value)
        except (AttributeError, TypeError, ValueError, KeyError):
            pass


class VideoWriter:
    """Streams frames into a video file, so long or very large videos never sit in memory twice.

    Audio (if any) is written first: it is small, and the muxer then never has to hold video back.
    """

    def __init__(self, path: str, width: int, height: int, fps: float, settings: EncoderSettings | None = None,
                 audio: np.ndarray | None = None, sample_rate: int = 0, stream_metadata: dict | None = None):
        import av

        self.settings = settings or EncoderSettings()
        self.path = path
        if width % 2 or height % 2:
            raise ValueError(f"Width and height must be even for {self.settings.pix_fmt} (got {width}x{height}).")
        self.container = av.open(path, mode="w")
        try:
            rate = Fraction(fps).limit_denominator(1001)
            self.stream = self.container.add_stream(self.settings.codec, rate=rate,
                                                    options=self.settings.video_options())
            self.stream.width, self.stream.height = width, height
            self.stream.pix_fmt = self.settings.pix_fmt
            _set_bt709(self.stream.codec_context)
            for key, value in (stream_metadata or {}).items():
                self.stream.metadata[key] = value  # e.g. stereo_mode for mkv
            if self.settings.codec in ("libx265", "hevc_nvenc") and self.settings.container in ("mp4", "mov"):
                self.stream.codec_tag = "hvc1"  # what Apple players and most headsets expect
            self.stream.codec_context.open()  # fail here (e.g. NVENC without NVIDIA) with a clear error
            if audio is not None and sample_rate > 0 and audio.size:
                self._write_audio(audio, sample_rate)
        except Exception as e:
            self.container.close()
            if os.path.exists(path):
                os.remove(path)
            raise RuntimeError(f"Could not start the encoder ({self.settings.codec}, {self.settings.pix_fmt}, "
                               f"audio {self.settings.audio_codec}): {e}") from e
        self.frames_written = 0

    def _write_audio(self, audio: np.ndarray, sample_rate: int) -> None:
        import av

        audio = np.ascontiguousarray(np.clip(audio[:2], -1.0, 1.0), dtype=np.float32)
        layout = "stereo" if audio.shape[0] == 2 else "mono"
        codec = self.settings.audio_codec
        if codec == "libopus" and sample_rate not in (8000, 12000, 16000, 24000, 48000):
            audio, sample_rate = _resample(audio, sample_rate, 48000), 48000
        stream = self.container.add_stream(codec, rate=sample_rate)
        stream.layout = layout
        if codec in ("aac", "libopus"):
            stream.bit_rate = self.settings.audio_bitrate_kbps * 1000
        # PyAV converts to the encoder's sample format and frame size as needed.
        step = 4096
        for start in range(0, audio.shape[1], step):
            frame = av.AudioFrame.from_ndarray(audio[:, start:start + step], format="fltp", layout=layout)
            frame.sample_rate = sample_rate
            frame.pts = start
            for packet in stream.encode(frame):
                self.container.mux(packet)
        for packet in stream.encode(None):
            self.container.mux(packet)

    def write(self, frames: np.ndarray) -> None:
        """frames: (B, H, W, 3) uint8, or uint16 (0..65535) for 10-bit output."""
        import av

        src_format = "rgb48le" if frames.dtype == np.uint16 else "rgb24"
        for arr in frames:
            frame = av.VideoFrame.from_ndarray(np.ascontiguousarray(arr), format=src_format)
            frame = _to_yuv(frame, self.settings.pix_fmt)
            frame.pts = self.frames_written
            for packet in self.stream.encode(frame):
                self.container.mux(packet)
            self.frames_written += 1

    def write_float(self, frames) -> None:
        """frames: (B, H, W, 3+) float 0..1, a torch tensor or numpy array (as ComfyUI IMAGE)."""
        self.write(float_to_ints(frames, self.settings.high_bit_depth))

    def close(self) -> None:
        for packet in self.stream.encode(None):
            self.container.mux(packet)
        self.container.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *exc):
        if exc_type is None:
            self.close()
        else:  # don't leave half a file behind
            try:
                self.container.close()
            finally:
                if os.path.exists(self.path):
                    os.remove(self.path)


def float_to_ints(frames, high_bit_depth: bool = False) -> np.ndarray:
    """ComfyUI IMAGE (B, H, W, C) 0..1 -> uint8 (or uint16 for 10-bit) RGB numpy."""
    if hasattr(frames, "detach"):
        frames = frames.detach()[..., :3].float().cpu().numpy()
    frames = np.clip(np.asarray(frames)[..., :3], 0.0, 1.0)
    if high_bit_depth:
        return (frames * 65535 + 0.5).astype(np.uint16)
    return (frames * 255 + 0.5).astype(np.uint8)


def _to_yuv(frame, pix_fmt: str):
    """RGB -> YUV with the BT.709 matrix (swscale would use BT.601 otherwise), limited range."""
    try:
        out = frame.reformat(format=pix_fmt, dst_colorspace="ITU709")
    except (TypeError, ValueError, KeyError, AttributeError):  # very old PyAV
        return frame.reformat(format=pix_fmt)
    _set_bt709(out)
    return out


def _resample(audio: np.ndarray, rate: int, new_rate: int) -> np.ndarray:
    n = int(round(audio.shape[1] * new_rate / rate))
    x_old = np.arange(audio.shape[1]) / rate
    x_new = np.arange(n) / new_rate
    return np.stack([np.interp(x_new, x_old, ch) for ch in audio]).astype(np.float32)


# ---- VR180 metadata (Spherical Video V2: st3d + sv3d boxes) -----------------------------------
# Players such as DeoVR, Skybox and HereSphere go by the file name (_180_LR), YouTube and ffmpeg
# read these boxes. They go inside the video sample entry (avc1/hvc1) in moov. Because the
# encoder writes moov after mdat, growing moov does not move any sample data.

_CONTAINERS_TO_ENTRY = ("trak", "mdia", "minf", "stbl", "stsd")


def _box(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", 8 + len(payload)) + kind + payload


def _full_box(kind: bytes, payload: bytes) -> bytes:
    return _box(kind, b"\0\0\0\0" + payload)


def vr180_boxes() -> bytes:
    """st3d (left-right) + sv3d with an equirectangular projection cropped to the front 180 degrees."""
    st3d = _full_box(b"st3d", bytes([2]))  # 2 = left-right
    svhd = _full_box(b"svhd", b"comfyui-promptgen\0")
    prhd = _full_box(b"prhd", struct.pack(">iii", 0, 0, 0))
    quarter = 0x40000000  # 0.32 fixed point: crop 25% from the left and the right of a 360 equirect
    equi = _full_box(b"equi", struct.pack(">IIII", 0, 0, quarter, quarter))
    sv3d = _box(b"sv3d", svhd + _box(b"proj", prhd + equi))
    return st3d + sv3d


def _children(data: bytes, start: int, end: int):
    """(offset, size, type) of the boxes between start and end."""
    pos = start
    while pos + 8 <= end:
        size, kind = struct.unpack(">I4s", data[pos:pos + 8])
        if size < 8 or pos + size > end:  # 0 / 1 (to end / 64-bit) don't occur inside moov here
            return
        yield pos, size, kind
        pos += size


def _is_video_trak(data: bytes, start: int, end: int) -> bool:
    for pos, size, kind in _children(data, start + 8, end):
        if kind == b"mdia":
            for p2, _s2, k2 in _children(data, pos + 8, pos + size):
                if k2 == b"hdlr":
                    return data[p2 + 16:p2 + 20] == b"vide"
    return False


def inject_vr180_metadata(path: str) -> bool:
    """Add VR180 SBS boxes to an MP4/MOV written by VideoWriter. Returns False if the layout is not
    the expected one (then the file is left as it is)."""
    with open(path, "rb") as f:
        data = f.read()
    top = list(_children(data, 0, len(data)))
    kinds = [k for _, _, k in top]
    if b"moov" not in kinds or b"mdat" not in kinds or kinds.index(b"moov") < kinds.index(b"mdat"):
        return False
    moov_pos, moov_size, _ = top[kinds.index(b"moov")]

    trak = next(((p, s) for p, s, k in _children(data, moov_pos + 8, moov_pos + moov_size)
                 if k == b"trak" and _is_video_trak(data, p, p + s)), None)
    if trak is None:
        return False
    path_offsets = [moov_pos]          # boxes whose size grows
    pos, size = trak
    for name in _CONTAINERS_TO_ENTRY[1:]:
        path_offsets.append(pos)
        found = next(((p, s) for p, s, k in _children(data, pos + 8, pos + size) if k == name.encode()), None)
        if found is None:
            return False
        pos, size = found
    path_offsets.append(pos)           # stsd (full box + entry count before the entries)
    entry_pos = pos + 16
    entry_size = struct.unpack(">I", data[entry_pos:entry_pos + 4])[0]
    if data[entry_pos + 4:entry_pos + 8] not in (b"avc1", b"hvc1", b"hev1"):
        return False
    path_offsets.append(entry_pos)

    extra = vr180_boxes()
    insert_at = entry_pos + entry_size
    out = bytearray(data[:insert_at] + extra + data[insert_at:])
    for offset in path_offsets:
        old = struct.unpack(">I", out[offset:offset + 4])[0]
        out[offset:offset + 4] = struct.pack(">I", old + len(extra))
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(out)
    os.replace(tmp, path)
    return True
