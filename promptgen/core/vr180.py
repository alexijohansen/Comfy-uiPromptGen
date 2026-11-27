"""Mono video + depth -> VR180 side-by-side stereo, by backward sampling (no splatting, no hole filling).

Model
-----
The source frame is treated as a pinhole camera (horizontal FOV -> focal length in pixels) looking
straight ahead. Each eye is a 180 x 180 degree half-equirectangular image. For every output pixel:

1. take its viewing direction d (longitude / latitude) and project it into the source camera:
   u0 = cx + f * dx/dz, v = cy + f * dy/dz. Outside the source frame stays black;
2. the eye sits at x = +-IPD/2. A point at depth Z seen along d from that eye lands in the source at
   u = u0 + f * eye_x / Z (pure horizontal disparity; infinity has no shift, as in VR180 cameras);
3. Z depends on where we sample, so look up depth at u, recompute u, and repeat a few times
   (fixed point iteration). Colour is then read with bilinear grid_sample, so there are never gaps:
   at depth edges the background stretches a little instead of leaving holes.

All depth handling works on inverse depth (1/metres): 0 means infinitely far (e.g. sky).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import torch
import torch.nn.functional as F

# ---- options shown on the nodes ---------------------------------------------------------------

# SBS total width x height. The per eye image is square (180 x 180 degrees): height x height.
RESOLUTION_PRESETS = {
    "2880x1440 (1440 per eye)": 1440,
    "3840x1920 (1920 per eye)": 1920,
    "4096x2048 (2048 per eye)": 2048,
    "5120x2560 (2560 per eye)": 2560,
    "5760x2880 (2880 per eye)": 2880,
    "7680x3840 (3840 per eye)": 3840,
    "8192x4096 (4096 per eye)": 4096,
    "match source sharpness": 0,
    "custom": -1,
}
MAX_EYE_SIZE = 4096  # 8192 px wide SBS is the most H.265 (level 6.2) and headsets decode

SENSOR_WIDTHS_MM = {
    "35 mm equivalent / full frame (36 mm)": 36.0,
    "Super 35 (24.9 mm)": 24.9,
    "APS-C (23.5 mm)": 23.5,
    "APS-C Canon (22.3 mm)": 22.3,
    "Micro Four Thirds (17.3 mm)": 17.3,
    "1 inch (13.2 mm)": 13.2,
}

DEPTH_FORMATS = [
    "metric depth (meters)",
    "DA3 Metric-Large raw",
    "relative depth (far = bigger)",
    "depth map, near = white",
    "disparity map, near = white",
]


@dataclass
class StereoSettings:
    hfov_deg: float = 65.0          # horizontal FOV of the source camera
    focal_mm: float = 0.0           # >0 overrides hfov_deg together with sensor_width_mm
    sensor_width_mm: float = 36.0
    fov_scale: float = 1.0          # multiplies the FOV the picture is shown at (fudge factor)
    ipd_mm: float = 64.0
    iterations: int = 3
    depth_blur_px: float = 0.0      # gaussian sigma in source pixels, applied to inverse depth
    eye_size: int = 2880

    def source_hfov_deg(self) -> float:
        if self.focal_mm > 0 and self.sensor_width_mm > 0:
            return math.degrees(2 * math.atan(self.sensor_width_mm / (2 * self.focal_mm)))
        return self.hfov_deg

    def shown_hfov_deg(self) -> float:
        return min(max(self.source_hfov_deg() * self.fov_scale, 1.0), 179.0)


def focal_px(width: int, hfov_deg: float) -> float:
    """Pinhole focal length in pixels for a frame this wide with this horizontal FOV."""
    return (width / 2) / math.tan(math.radians(hfov_deg) / 2)


def eye_size_for(preset: str, custom_eye_size: int, src_width: int, settings: StereoSettings) -> int:
    """Per eye size in pixels (multiple of 16) for a resolution preset."""
    size = RESOLUTION_PRESETS.get(preset, -1)
    if size == 0:  # same pixels per degree as the centre of the source
        size = focal_px(src_width, settings.shown_hfov_deg()) * math.pi
    elif size < 0:
        size = custom_eye_size
    return int(min(max(round(size / 16) * 16, 64), MAX_EYE_SIZE))


# ---- depth -> inverse metres -----------------------------------------------------------------

def to_inverse_depth(depth: torch.Tensor, depth_format: str, *, depth_scale: float = 1.0,
                     near_m: float = 0.5, far_m: float = 20.0, reference_m: float = 3.0,
                     min_depth_m: float = 0.2, da3_factor: float = 1.0,
                     sky: torch.Tensor | None = None) -> torch.Tensor:
    """Inverse depth in 1/metres, (B, H, W) float32, 0 = infinitely far.

    depth: (B, H, W) values in the given format. For the image formats ("near = white") they are
    0..1. depth_scale multiplies the final metric depth (bigger = world looks bigger/farther, less 3D).
    min_depth_m caps how close anything can be, which limits the largest shift.
    da3_factor converts DA3 Metric-Large raw output to metres (see da3_metric_factor).
    sky: optional (B, H, W) probability; > 0.5 is pushed to infinity.
    """
    d = depth.float()
    if depth_format == "metric depth (meters)":
        inv = 1.0 / d.clamp(min=1e-6)
    elif depth_format == "DA3 Metric-Large raw":
        inv = 1.0 / (d * da3_factor).clamp(min=1e-6)
    elif depth_format == "relative depth (far = bigger)":
        valid = d[(sky <= 0.5) & (d > 0)] if sky is not None else d[d > 0]
        median = _median(valid) if valid.numel() else 1.0
        inv = 1.0 / (d * (reference_m / max(median, 1e-6))).clamp(min=1e-6)
    elif depth_format == "depth map, near = white":
        z = far_m - d.clamp(0, 1) * (far_m - near_m)
        inv = 1.0 / z.clamp(min=1e-6)
    elif depth_format == "disparity map, near = white":
        inv = d.clamp(0, 1) * (1 / near_m - 1 / far_m) + 1 / far_m
    else:
        raise ValueError(f"Unknown depth format '{depth_format}'. Use one of: {', '.join(DEPTH_FORMATS)}")
    inv = inv / max(depth_scale, 1e-6)
    inv = inv.clamp(0.0, 1.0 / max(min_depth_m, 1e-3))
    if sky is not None:
        inv = torch.where(sky.float() > 0.5, torch.zeros_like(inv), inv)
    return inv


def _median(values: torch.Tensor, max_samples: int = 1_000_000) -> float:
    values = values.flatten()
    if values.numel() > max_samples:
        values = values[torch.randint(0, values.numel(), (max_samples,))]
    return float(values.median())


def da3_metric_factor(src_width: int, src_height: int, hfov_deg: float, da3_resolution: int) -> float:
    """DA3 Metric-Large: metres = raw * focal / 300, focal in pixels at the resolution DA3 ran at
    (longest side = da3_resolution with ComfyUI's default upper_bound_resize)."""
    process_width = src_width * da3_resolution / max(src_width, src_height)
    return focal_px(process_width, hfov_deg) / 300.0


def temporal_smooth(inv: torch.Tensor, amount: float) -> torch.Tensor:
    """Exponential moving average over frames (0 = off, 0.9 = very smooth). Reduces depth flicker."""
    if amount <= 0 or inv.shape[0] < 2:
        return inv
    out = inv.clone()
    for i in range(1, out.shape[0]):
        out[i] = amount * out[i - 1] + (1 - amount) * inv[i]
    return out


def match_depth_size(inv: torch.Tensor, height: int, width: int) -> torch.Tensor:
    """Resize inverse depth (B, h, w) to the frame size (bilinear)."""
    if inv.shape[-2:] == (height, width):
        return inv
    return F.interpolate(inv[:, None], size=(height, width), mode="bilinear", align_corners=False)[:, 0]


def gaussian_blur(x: torch.Tensor, sigma: float) -> torch.Tensor:
    """Separable gaussian blur of (B, 1, H, W)."""
    if sigma <= 0:
        return x
    radius = max(1, int(math.ceil(sigma * 3)))
    t = torch.arange(-radius, radius + 1, device=x.device, dtype=x.dtype)
    k = torch.exp(-0.5 * (t / sigma) ** 2)
    k = k / k.sum()
    x = F.conv2d(F.pad(x, (radius, radius, 0, 0), mode="replicate"), k.view(1, 1, 1, -1))
    return F.conv2d(F.pad(x, (0, 0, radius, radius), mode="replicate"), k.view(1, 1, -1, 1))


# ---- rendering -------------------------------------------------------------------------------

def _eye_rays(size: int, device, dtype=torch.float32):
    """Normalised pinhole coordinates (dx/dz, dy/dz) and a valid mask for a 180x180 half-equirect."""
    t = (torch.arange(size, device=device, dtype=dtype) + 0.5) / size - 0.5
    lon, lat = t * math.pi, t * math.pi
    lat, lon = torch.meshgrid(lat, lon, indexing="ij")  # (size, size), rows = latitude (down)
    dx = torch.cos(lat) * torch.sin(lon)
    dy = torch.sin(lat)
    dz = torch.cos(lat) * torch.cos(lon)
    valid = dz > 1e-4
    dz = dz.clamp(min=1e-4)
    return dx / dz, dy / dz, valid


def render_sbs(frames: torch.Tensor, inv_depth: torch.Tensor, settings: StereoSettings) -> torch.Tensor:
    """Render left|right half-equirect eyes. frames (B, H, W, 3) 0..1, inv_depth (B, H, W) 1/metres,
    both on the device to render on. Returns (B, eye, 2 * eye, 3) float 0..1."""
    B, H, W, _ = frames.shape
    n = settings.eye_size
    f = focal_px(W, settings.shown_hfov_deg())
    xn, yn, valid = _eye_rays(n, frames.device)
    u0 = W / 2 + f * xn                     # source pixel coords (pixel centres at i + 0.5)
    v = H / 2 + f * yn
    gy = (v / H * 2 - 1).expand(B, n, n)
    gy = torch.where(valid, gy, torch.full_like(gy, -3.0))  # behind the camera -> outside -> black

    img = frames.permute(0, 3, 1, 2).contiguous()           # (B, 3, H, W)
    inv = gaussian_blur(inv_depth[:, None].float(), settings.depth_blur_px)

    eyes = []
    for eye_x in (-settings.ipd_mm / 2000.0, settings.ipd_mm / 2000.0):  # left, right (metres)
        shift_scale = f * eye_x                             # source px per (1/metre)
        u = u0.expand(B, n, n)
        for _ in range(max(1, settings.iterations)):
            grid = torch.stack([u / W * 2 - 1, gy], dim=-1)
            z_inv = F.grid_sample(inv, grid, mode="bilinear", padding_mode="border", align_corners=False)[:, 0]
            u = u0 + shift_scale * z_inv
        grid = torch.stack([u / W * 2 - 1, gy], dim=-1)
        eyes.append(F.grid_sample(img, grid, mode="bilinear", padding_mode="zeros", align_corners=False))
    return torch.cat(eyes, dim=3).permute(0, 2, 3, 1).clamp(0, 1)


class StereoClip:
    """A clip to render later, chunk by chunk (what the Stereo node hands to the Save node).

    Rendering everything up front would need e.g. 350 MB per 7680x3840 frame as a float image,
    so the Save node renders a few frames at a time and streams them into the encoder.
    """

    def __init__(self, frames: torch.Tensor, inv_depth: torch.Tensor, settings: StereoSettings,
                 chunk_size: int = 4, device=None):
        self.frames = frames          # (B, H, W, 3) CPU float
        self.inv_depth = inv_depth    # (B or 1, H, W) CPU float
        self.settings = settings
        self.chunk_size = max(1, int(chunk_size))
        self.device = device or torch.device("cpu")

    def __len__(self) -> int:
        return self.frames.shape[0]

    @property
    def size(self) -> tuple[int, int]:
        """(width, height) of the SBS output."""
        return 2 * self.settings.eye_size, self.settings.eye_size

    def render(self, start: int, end: int) -> torch.Tensor:
        """Frames start..end-1 as (b, eye, 2*eye, 3) float 0..1 on the render device."""
        frames = self.frames[start:end].to(self.device, torch.float32)
        inv = self.inv_depth if self.inv_depth.shape[0] == 1 else self.inv_depth[start:end]
        inv = inv.to(self.device, torch.float32).expand(frames.shape[0], -1, -1)
        inv = match_depth_size(inv, frames.shape[1], frames.shape[2])
        with torch.no_grad():
            return render_sbs(frames[..., :3], inv, self.settings)

    def chunks(self, high_bit_depth: bool = False):
        """Yield (b, eye, 2*eye, 3) numpy arrays, chunk_size frames at a time: uint8, or uint16 for
        10-bit output."""
        scale, dtype = (65535, torch.int32) if high_bit_depth else (255, torch.uint8)
        for start in range(0, len(self), self.chunk_size):
            out = self.render(start, min(start + self.chunk_size, len(self)))
            out = (out * scale + 0.5).clamp(0, scale).to(dtype).cpu().numpy()
            yield out.astype("uint16") if high_bit_depth else out
