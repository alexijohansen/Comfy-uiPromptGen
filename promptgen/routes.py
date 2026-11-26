"""Web routes used by the frontend scripts in js/."""

from __future__ import annotations

from .comfy import output_dir
from .core.textfiles import list_text_files, resolve_folder

try:
    from aiohttp import web
    from server import PromptServer
except ImportError:  # outside ComfyUI
    PromptServer = None

if PromptServer is not None:

    @PromptServer.instance.routes.get("/promptgen/count_files")
    async def count_files(request):
        """How many .txt files are in ?folder=... (used by the 'Queue all files' button)."""
        try:
            path = resolve_folder(request.query.get("folder", ""), output_dir())
            return web.json_response({"total": len(list_text_files(path)), "folder": path})
        except (OSError, ValueError) as e:
            return web.json_response({"error": str(e)}, status=400)
