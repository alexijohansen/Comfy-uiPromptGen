// Show / Save Text and Save Settings: show the text and the saved file name on the node after a run.
// Depth to VR180 Stereo: show its info text.
import { app } from "../../scripts/app.js";
import { NODES, chain, readOnlyBox, redraw } from "./common.js";

const join = (value) => (Array.isArray(value) ? value.join("\n") : String(value ?? ""));

app.registerExtension({
    name: "promptgen.showText",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name === NODES.stereo) {
            chain(nodeType, "onExecuted", function (message) {
                readOnlyBox(this, "info_text", { maxLines: 4 }).value = join(message?.text);
                redraw(this);
            });
            return;
        }
        if (![NODES.showText, NODES.saveSettings].includes(nodeData.name)) return;

        chain(nodeType, "onExecuted", function (message) {
            readOnlyBox(this, "saved_file", { maxLines: 2 }).value = "File: " + join(message?.saved_file);
            readOnlyBox(this, "shown_text").value = join(message?.text);
            redraw(this);
        });
    },
});
