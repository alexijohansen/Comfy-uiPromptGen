"""comfyui-promptgen: random prompt generator nodes for ComfyUI."""

WEB_DIRECTORY = "./js"

# ComfyUI imports this folder as a package. pytest may import this file on its own
# (the folder name has a '-'), in which case there is no package and nothing to register.
if __package__:
    from .promptgen import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
    from .promptgen import routes  # noqa: F401  (registers the web route used by the UI)

    __all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
