// Batch Text / Image / Video Loader: "Queue all files" / "images" / "videos" button. Counts the files left
// in the folder (from index to the end) and queues that many runs.
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { NODES, chain, getWidget, notify } from "./common.js";

// node ID -> what the button counts (matches KINDS in promptgen/routes.py)
const BUTTONS = {
    [NODES.batchText]: { kind: "text", title: "Queue all files", noun: "files" },
    [NODES.batchImage]: { kind: "images", title: "Queue all images", noun: "images" },
    [NODES.batchVideo]: { kind: "videos", title: "Queue all videos", noun: "videos" },
};

async function countFiles(folder, kind) {
    const query = `folder=${encodeURIComponent(folder)}&kind=${kind}`;
    const res = await api.fetchApi(`/promptgen/count_files?${query}`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    return data.total;
}

async function queueAll(node, { kind, title, noun }) {
    if (getWidget(node, "auto_increment")?.value === false) {
        notify("warn", title, `Turn auto_increment on first, or every run loads the same ${noun.slice(0, -1)}.`);
        return;
    }
    const index = Number(getWidget(node, "index")?.value ?? 0);
    let total;
    try {
        total = await countFiles(getWidget(node, "folder")?.value ?? "", kind);
    } catch (e) {
        notify("error", title, String(e.message ?? e));
        return;
    }
    const remaining = getWidget(node, "when_done")?.value === "start over" ? total : total - index;
    if (remaining <= 0) {
        notify("warn", title, `All ${total} ${noun} are done. Set index back to 0 to start again.`);
        return;
    }
    notify("info", title, `Queueing ${remaining} run(s), ${noun} ${index + 1}-${index + remaining} of ${total}.`);
    await app.queuePrompt(0, remaining);
}

app.registerExtension({
    name: "promptgen.queueAllFiles",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        const button = BUTTONS[nodeData.name];
        if (!button) return;
        chain(nodeType, "onNodeCreated", function () {
            const widget = this.addWidget("button", button.title, null, () => queueAll(this, button));
            widget.serialize = false; // keeps the saved widget values unchanged
        });
    },
});
