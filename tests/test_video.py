"""Video reading/writing, VR180 metadata and the video nodes, end to end on tiny files."""

import json
import subprocess
import shutil
from fractions import Fraction
from types import SimpleNamespace

import numpy as np
import pytest

av = pytest.importorskip("av")
torch = pytest.importorskip("torch")

from promptgen import comfy  # noqa: E402
from promptgen.core.filenames import unique_file_path  # noqa: E402
from promptgen.core.video import (AUDIO_CODECS, EncoderSettings, VideoWriter, inject_vr180_metadata,  # noqa: E402
                                  read_video, vr180_boxes)

SR = 44100


def _tone(seconds, rate=SR):
    t = np.arange(int(seconds * rate)) / rate
    return np.stack([np.sin(2 * np.pi * 440 * t), np.sin(2 * np.pi * 660 * t)]).astype(np.float32) * 0.3


def _write(path, frames=24, size=(64, 32), fps=24, audio=True, settings=None):
    settings = settings or EncoderSettings(preset="ultrafast")
    with VideoWriter(str(path), size[0], size[1], fps, settings, _tone(frames / fps) if audio else None, SR) as w:
        w.write((np.random.rand(frames, size[1], size[0], 3) * 255).astype(np.uint8))
    return path


@pytest.fixture
def out(tmp_path, monkeypatch):
    for module in ("promptgen.nodes.batch", "promptgen.nodes.video"):
        monkeypatch.setattr(f"{module}.output_dir", lambda: str(tmp_path))
    monkeypatch.setattr(comfy, "output_dir", lambda: str(tmp_path))
    return tmp_path


def test_write_and_read_back_with_trim(tmp_path):
    path = _write(tmp_path / "a.mp4", frames=30, fps=30)
    v = read_video(str(path), start_frame=10, max_frames=10)
    assert len(v.frames) == 10 and v.frames[0].shape == (32, 64, 3) and v.fps == pytest.approx(30)
    assert v.audio.shape[0] == 2 and v.audio.shape[1] == pytest.approx(SR / 3, abs=50)
    assert read_video(str(_write(tmp_path / "b.mp4", audio=False))).audio is None


@pytest.mark.parametrize("audio_codec", list(AUDIO_CODECS))
def test_every_audio_codec_in_a_container_that_takes_it(tmp_path, audio_codec):
    container = AUDIO_CODECS[audio_codec][1][-1]
    s = EncoderSettings.from_widgets("h264 (libx264)", 0, "ultrafast", "yuv444p10le", audio_codec, 320, container)
    path = _write(tmp_path / f"x.{container}", settings=s)
    v = read_video(str(path))
    assert len(v.frames) == 24 and v.audio is not None


def test_bad_combination_is_explained():
    with pytest.raises(ValueError, match="can't go in .mp4"):
        EncoderSettings.from_widgets("h264 (libx264)", 16, "slow", "yuv420p", "pcm 24-bit (uncompressed)", 320, "mp4")


def test_failed_encoder_leaves_no_file(tmp_path):
    s = EncoderSettings(codec="no_such_encoder")
    with pytest.raises(Exception):
        VideoWriter(str(tmp_path / "x.mp4"), 64, 32, 24, s)
    assert not (tmp_path / "x.mp4").exists()


@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="needs ffprobe")
def test_vr180_metadata_is_read_by_ffmpeg(tmp_path):
    path = _write(tmp_path / "v_180_LR.mp4", settings=EncoderSettings(codec="libx265", preset="ultrafast"))
    assert inject_vr180_metadata(str(path))
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", str(path)],
                                      capture_output=True, text=True, check=True).stdout)
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    kinds = {d["side_data_type"]: d for d in video.get("side_data_list", [])}
    assert kinds["Stereo 3D"]["type"] == "side by side"
    assert "equirectangular" in kinds["Spherical Mapping"]["projection"]
    assert len(read_video(str(path)).frames) == 24  # still plays


def test_vr180_boxes_layout():
    boxes = vr180_boxes()
    assert boxes[4:8] == b"st3d" and boxes[12] == 2 and b"sv3d" in boxes and b"equi" in boxes


def test_unique_file_path(tmp_path):
    p1 = unique_file_path("vr180/", "clip", str(tmp_path), ".mp4", suffix="_180_LR")
    assert p1.replace("\\", "/").endswith("vr180/clip_180_LR.mp4")
    open(p1, "w").close()
    assert unique_file_path("vr180/", "clip", str(tmp_path), ".mp4", suffix="_180_LR").endswith("clip_2_180_LR.mp4")
    assert unique_file_path("vr180/", None, str(tmp_path), ".mp4", default_prefix="vr180/vr180").replace(
        "\\", "/").endswith("vr180/vr180_00001.mp4")
    assert unique_file_path("video/ComfyUI", None, str(tmp_path), ".mkv").endswith("ComfyUI_00001.mkv")


def test_batch_video_loader(out):
    folder = out / "clips"
    folder.mkdir()
    _write(folder / "b.mp4", frames=6)
    _write(folder / "a.mov", frames=12, audio=False)
    (folder / "notes.txt").write_text("x")
    from promptgen.nodes.video import PromptGenBatchVideo

    node = PromptGenBatchVideo()
    frames, fps, audio, name, index, total = node.run("clips", 0, True, "stop", unique_id="1",
                                                      start_frame=2, max_frames=5)["result"]
    assert (tuple(frames.shape), name, index, total, audio) == ((5, 32, 64, 3), "a", 0, 2, None)
    assert frames.dtype == torch.float32 and 0 <= float(frames.min()) and float(frames.max()) <= 1
    second = node.run("clips", 0, True, "stop", unique_id="1", start_frame=0, max_frames=0)
    frames, fps, audio, name = second["result"][:4]
    assert name == "b" and frames.shape[0] == 6 and audio["waveform"].shape[:2] == (1, 2)
    assert audio["sample_rate"] == SR and second["ui"]["next_number"] == [2]


def _fake_video(frames, fps=24, audio=None):
    return SimpleNamespace(get_components=lambda: SimpleNamespace(images=frames, audio=audio,
                                                                  frame_rate=Fraction(fps)))


def test_save_video_hq(out):
    from promptgen.nodes.video import PromptGenSaveVideoHQ, encoder_inputs

    widgets = {k: v[1]["default"] for k, v in encoder_inputs().items()}
    widgets.update(preset="ultrafast", audio_codec="alac (lossless)")
    audio = {"waveform": torch.from_numpy(_tone(2))[None], "sample_rate": SR}
    frames = torch.rand(10, 33, 65, 3)  # odd sizes are cropped to even
    ui = PromptGenSaveVideoHQ().run(_fake_video(frames, audio=audio), "video/test", None, **widgets)["ui"]
    assert ui["images"][0]["subfolder"] == "video" and ui["images"][0]["filename"] == "test_00001.mp4"
    v = read_video(str(out / "video" / "test_00001.mp4"))
    assert len(v.frames) == 10 and v.frames[0].shape == (32, 64, 3)
    assert v.audio.shape[1] == pytest.approx(SR * 10 / 24, abs=SR * 0.05)  # cut to the video's length


def test_stereo_then_save_vr180(out):
    from promptgen.nodes.video import PromptGenSaveVR180, PromptGenVR180Stereo, encoder_inputs

    stereo_inputs = PromptGenVR180Stereo.INPUT_TYPES()["required"]
    kw = {k: v[1]["default"] for k, v in stereo_inputs.items()}
    kw.update(resolution="custom", custom_eye_size=128, depth_format="metric depth (meters)")
    frames = torch.rand(3, 36, 64, 3)
    geometry = {"depth": torch.full((3, 36, 64), 2.0), "image": frames, "mode": "mono",
                "sky": torch.zeros(3, 36, 64)}
    result = PromptGenVR180Stereo().run(**kw, da3_geometry=geometry)
    clip, preview, info, debug = result["result"]
    assert debug.shape == (1, 128, 128, 3)  # anaglyph of one eye
    assert preview.shape == (1, 128, 256, 3) and "SBS 256x128" in info and result["ui"]["text"] == [info]

    widgets = {k: v[1]["default"] for k, v in encoder_inputs(codec="h265 (libx265)").items()}
    widgets["preset"] = "ultrafast"
    audio = {"waveform": torch.from_numpy(_tone(1))[None], "sample_rate": SR}
    res = PromptGenSaveVR180().run(clip, 24.0, "vr180/", True, True, audio=audio, name="my clip", **widgets)
    assert res["ui"]["saved_file"] == ["vr180/my clip_180_LR.mp4"]
    v = read_video(res["result"][0])
    assert len(v.frames) == 3 and v.frames[0].shape == (128, 256, 3) and v.audio is not None


def test_stereo_needs_depth():
    from promptgen.nodes.video import PromptGenVR180Stereo

    kw = {k: v[1]["default"] for k, v in PromptGenVR180Stereo.INPUT_TYPES()["required"].items()}
    with pytest.raises(ValueError, match="depth"):
        PromptGenVR180Stereo().run(**kw, images=torch.rand(1, 8, 8, 3))
