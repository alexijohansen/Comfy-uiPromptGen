"""Stereo maths: projection, disparity, depth formats and chunked rendering."""

import math

import pytest

torch = pytest.importorskip("torch")

from promptgen.core import vr180  # noqa: E402


def _line_centre_deg(row, n):
    """Longitude (degrees) of the brightness centroid in one eye's row."""
    cols = torch.arange(n, dtype=torch.float32)
    c = float((row * cols).sum() / row.sum())
    return ((c + 0.5) / n - 0.5) * 180


def test_disparity_matches_ipd_over_depth():
    # 90° camera, 200 px wide -> f = 100 px. Plane at 1 m, IPD 64 mm -> each eye shifts 32 mm / 1 m.
    frames = torch.zeros(1, 100, 200, 3)
    frames[:, :, 99:101] = 1.0
    inv = torch.ones(1, 100, 200)
    s = vr180.StereoSettings(hfov_deg=90, ipd_mm=64, eye_size=1800, depth_blur_px=0)
    out = vr180.render_sbs(frames, inv, s)[0]
    assert out.shape == (1800, 3600, 3)
    expected = math.degrees(math.atan(0.032))
    left, right = _line_centre_deg(out[900, :1800, 0], 1800), _line_centre_deg(out[900, 1800:, 0], 1800)
    assert left == pytest.approx(expected, abs=0.02)   # near things move right in the left eye
    assert right == pytest.approx(-expected, abs=0.02)


def test_infinity_has_no_shift_and_outside_is_black():
    frames = torch.rand(1, 60, 80, 3)
    inv = torch.zeros(1, 60, 80)  # everything at infinity
    s = vr180.StereoSettings(hfov_deg=60, eye_size=256)
    out = vr180.render_sbs(frames, inv, s)[0]
    assert torch.allclose(out[:, :256], out[:, 256:])
    assert out[0, 0].abs().sum() == 0 and out[128, 0].abs().sum() == 0  # corners/edges of the dome
    assert out[128, 128].sum() > 0  # the centre shows the picture


def test_no_holes_at_depth_edges():
    frames = torch.rand(1, 64, 64, 3) * 0.5 + 0.5  # never black inside the frame
    inv = torch.full((1, 64, 64), 0.1)
    inv[:, :, 24:40] = 1 / 0.3  # a very close bar
    s = vr180.StereoSettings(hfov_deg=60, ipd_mm=64, eye_size=512, iterations=3, depth_blur_px=0)
    out = vr180.render_sbs(frames, inv, s)[0]
    centre = out[200:312, 200:312]  # well inside the source frame, left eye
    assert torch.isfinite(out).all() and centre.min() > 0.4


def test_depth_formats():
    d = torch.tensor([[[0.0, 0.5, 1.0]]])
    inv = vr180.to_inverse_depth(d, "disparity map, near = white", near_m=0.5, far_m=10, min_depth_m=0.1)
    assert inv[0, 0].tolist() == pytest.approx([1 / 10, 0.5 * (2 - 0.1) + 0.1, 2.0])
    inv = vr180.to_inverse_depth(d, "depth map, near = white", near_m=1, far_m=11, min_depth_m=0.1)
    assert (1 / inv[0, 0]).tolist() == pytest.approx([11, 6, 1])
    m = torch.tensor([[[2.0, 4.0]]])
    assert vr180.to_inverse_depth(m, "metric depth (meters)", depth_scale=2)[0, 0].tolist() == pytest.approx([0.25, 0.125])
    rel = vr180.to_inverse_depth(torch.tensor([[[1.0, 2.0, 3.0]]]), "relative depth (far = bigger)", reference_m=4)
    assert (1 / rel[0, 0]).tolist() == pytest.approx([2, 4, 6])
    sky = torch.tensor([[[0.0, 0.9]]])
    assert vr180.to_inverse_depth(m, "metric depth (meters)", sky=sky)[0, 0, 1] == 0
    assert vr180.to_inverse_depth(torch.tensor([[[0.01]]]), "metric depth (meters)", min_depth_m=0.5)[0, 0, 0] == 2.0
    with pytest.raises(ValueError):
        vr180.to_inverse_depth(m, "nonsense")


def test_da3_metric_factor_and_fov():
    # 1920x1080, DA3 at 504: process width 504, 90° -> f = 252 px -> metres = raw * 252 / 300
    assert vr180.da3_metric_factor(1920, 1080, 90, 504) == pytest.approx(252 / 300)
    s = vr180.StereoSettings(focal_mm=18, sensor_width_mm=36)
    assert s.source_hfov_deg() == pytest.approx(90)
    s.fov_scale = 1.1
    assert s.shown_hfov_deg() == pytest.approx(99)


def test_resolution_presets():
    s = vr180.StereoSettings(hfov_deg=65)
    assert vr180.eye_size_for("5760x2880 (2880 per eye)", 0, 2276, s) == 2880
    assert vr180.eye_size_for("custom", 1010, 2276, s) == 1008  # rounded to a multiple of 16
    assert vr180.eye_size_for("match source sharpness", 0, 2276, s) == vr180.MAX_EYE_SIZE  # capped
    assert vr180.eye_size_for("match source sharpness", 0, 640, s) == 1584


def test_clip_renders_in_chunks_with_low_res_depth():
    frames = torch.rand(5, 32, 48, 3)
    inv = torch.full((5, 8, 12), 0.5)  # depth at a lower resolution than the frames
    clip = vr180.StereoClip(frames, inv, vr180.StereoSettings(eye_size=64), chunk_size=2)
    chunks = list(clip.chunks())
    assert [c.shape[0] for c in chunks] == [2, 2, 1]
    assert chunks[0].shape == (2, 64, 128, 3) and str(chunks[0].dtype) == "uint8"
    assert clip.size == (128, 64)
    assert str(next(clip.chunks(high_bit_depth=True)).dtype) == "uint16"


def test_temporal_smoothing():
    inv = torch.tensor([[[0.0]], [[1.0]], [[1.0]]])
    assert vr180.temporal_smooth(inv, 0.5)[:, 0, 0].tolist() == pytest.approx([0.0, 0.5, 0.75])
    assert vr180.temporal_smooth(inv, 0) is inv


def test_clamp_near_outliers():
    inv = torch.cat([torch.full((999,), 0.5), torch.tensor([50.0])])[None, None]
    out, limit = vr180.clamp_near_outliers(inv, 0.5)
    assert limit == pytest.approx(0.5) and float(out.max()) == pytest.approx(0.5)
    assert vr180.clamp_near_outliers(inv, 0)[0] is inv


def test_ray_march_has_no_echoes_at_depth_edges():
    # A near disc over a far, striped background with a soft depth edge (like real depth models).
    H, W = 120, 200
    yy, xx = torch.meshgrid(torch.arange(H), torch.arange(W), indexing="ij")
    fg = (xx - 100) ** 2 + (yy - 60) ** 2 < 30 ** 2
    frames = torch.where(fg[..., None], torch.tensor([0.0, 1.0, 0.0]), torch.tensor([1.0, 0.0, 0.0]))[None]
    inv = vr180.gaussian_blur(torch.where(fg, 1 / 0.5, 1 / 8.0)[None, None].float(), 2)[:, 0]
    s = vr180.StereoSettings(hfov_deg=60, eye_size=512, depth_blur_px=0)
    def disc_row(ipd):
        row = vr180.render_eyes(frames, inv, s, ipd_mm=ipd)[0][0][256, :, 1]  # green through the disc
        return (row > 0.5).nonzero().flatten()

    flat, left = disc_row(0), disc_row(64)
    # one solid run (no echoes), and as wide as without stereo (the fixed point method eats into it)
    assert int(left[-1] - left[0] + 1) == left.numel()
    assert abs(left.numel() - flat.numel()) <= 3


def test_debug_views_render():
    frames, inv = torch.rand(1, 40, 60, 3), torch.full((1, 40, 60), 0.5)
    s = vr180.StereoSettings(eye_size=64)
    for view in vr180.DEBUG_VIEWS:
        out = vr180.render_debug(frames, inv, s, view)
        assert out.shape == (1, 64, 64, 3) and torch.isfinite(out).all(), view
