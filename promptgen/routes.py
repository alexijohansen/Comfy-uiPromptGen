"""Web routes used by the frontend scripts in js/."""

from __future__ import annotations

from .comfy import output_dir
from .core.textfiles import IMAGE_EXTENSIONS, TEXT_EXTENSIONS, list_files, resolve_folder

KINDS = {"text": TEXT_EXTENSIONS, "images": IMAGE_EXTENSIONS}

try:
    from aiohttp import web
    from server import PromptServer
except ImportError:  # outside ComfyUI
    PromptServer = None

if PromptServer is not None:

    @PromptServer.instance.routes.get("/promptgen/count_files")
    async def count_files(request):
        """How many files are in ?folder=...&kind=text|images (used by the 'Queue all' buttons)."""
        try:
            extensions = KINDS.get(request.query.get("kind", "text"), TEXT_EXTENSIONS)
            path = resolve_folder(request.query.get("folder", ""), output_dir())
            return web.json_response({"total": len(list_files(path, extensions)), "folder": path})
        except (OSError, ValueError) as e:
            return web.json_response({"error": str(e)}, status=400)
