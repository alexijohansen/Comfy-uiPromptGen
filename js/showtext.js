import { app } from "../../scripts/app.js";
import { ComfyWidgets } from "../../scripts/widgets.js";

// Shows the text received by "PromptGen Show / Save Text" in a read-only box on the node,
// plus the file it was saved to.

function readOnlyBox(node, name) {
    let widget = node.widgets?.find((w) => w.name === name);
    if (!widget) {
        widget = ComfyWidgets["STRING"](node, name, ["STRING", { multiline: true }], app).widget;
        if (widget.inputEl) {
            widget.inputEl.readOnly = true;
            widget.inputEl.style.opacity = 0.7;
        }
        widget.serialize = false; // display only, not sent to the backend
    }
    return widget;
}

app.registerExtension({
    name: "promptgen.showText",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!["PromptGenShowText", "PromptGenSaveSettings"].includes(nodeData.name)) return;

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            onExecuted?.apply(this, arguments);
            const join = (v) => (Array.isArray(v) ? v.join("\n") : String(v ?? ""));
            const fileBox = readOnlyBox(this, "saved_file");
            const textBox = readOnlyBox(this, "shown_text");
            fileBox.value = "File: " + join(message?.saved_file);
            textBox.value = join(message?.text);
            this.setDirtyCanvas?.(true, true);
        };
    },
});
