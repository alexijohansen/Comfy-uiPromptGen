// Shared helpers for the PromptGen frontend scripts. Has no extension of its own.
import { app } from "../../scripts/app.js";
import { ComfyWidgets } from "../../scripts/widgets.js";

// Node IDs, as registered in promptgen/__init__.py.
export const NODES = {
    template: "PromptGenTemplate",
    showText: "PromptGenShowText",
    counter: "PromptGenCounter",
    batchText: "PromptGenBatchText",
    batchImage: "PromptGenBatchImage",
    batchVideo: "PromptGenBatchVideo",
    stereo: "PromptGenVR180",
    stereoOld: "PromptGenVR180Stereo",
    saveSettings: "PromptGenSaveSettings",
};

export function getWidget(node, name) {
    return node.widgets?.find((w) => w.name === name);
}

export function redraw(node) {
    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

const LINE_HEIGHT_PX = 18;

// A read-only multiline text box on the node, created on first use. Not saved with the workflow.
// maxLines limits its height (e.g. 2 for a file name); without it the box takes the free space.
export function readOnlyBox(node, name, { maxLines } = {}) {
    let widget = getWidget(node, name);
    if (!widget) {
        widget = ComfyWidgets["STRING"](node, name, ["STRING", { multiline: true }], app).widget;
        if (widget.inputEl) {
            widget.inputEl.readOnly = true;
            widget.inputEl.style.opacity = 0.7;
        }
        if (maxLines) {
            const height = maxLines * LINE_HEIGHT_PX + 8;
            widget.options = widget.options ?? {};
            widget.options.getMinHeight = () => height;
            widget.options.getMaxHeight = () => height;
            if (widget.inputEl) {
                widget.inputEl.rows = maxLines;
                widget.inputEl.style.minHeight = widget.inputEl.style.maxHeight = `${height}px`;
            }
        }
        widget.serialize = false;
    }
    return widget;
}

// Chain a method on a node type's prototype, keeping any existing one.
export function chain(nodeType, method, fn) {
    const original = nodeType.prototype[method];
    nodeType.prototype[method] = function () {
        const result = original?.apply(this, arguments);
        fn.apply(this, arguments);
        return result;
    };
}

// A small popup message (falls back to the console).
export function notify(severity, summary, detail) {
    const toast = app.extensionManager?.toast;
    if (toast?.add) toast.add({ severity, summary, detail, life: 5000 });
    else console[severity === "error" ? "error" : "log"](`[PromptGen] ${summary}: ${detail}`);
}
