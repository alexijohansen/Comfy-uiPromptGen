// Batch Text Loader: "Queue all files" button. Counts the .txt files left in the folder
// (from index to the end) and queues that many runs.
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { NODES, chain, getWidget, notify } from "./common.js";

const TITLE = "Queue all files";

async function countFiles(folder) {
    const res = await api.fetchApi(`/promptgen/count_files?folder=${encodeURIComponent(folder)}`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    return data.total;
}

async function queueAllFiles(node) {
    if (getWidget(node, "auto_increment")?.value === false) {
        notify("warn", TITLE, "Turn auto_increment on first, or every run loads the same file.");
        return;
    }
    const index = Number(getWidget(node, "index")?.value ?? 0);
    let total;
    try {
        total = await countFiles(getWidget(node, "folder")?.value ?? "");
    } catch (e) {
        notify("error", TITLE, String(e.message ?? e));
        return;
    }
    const remaining = getWidget(node, "when_done")?.value === "start over" ? total : total - index;
    if (remaining <= 0) {
        notify("warn", TITLE, `All ${total} files are done. Set index back to 0 to start again.`);
        return;
    }
    notify("info", TITLE, `Queueing ${remaining} run(s), files ${index + 1}-${index + remaining} of ${total}.`);
    await app.queuePrompt(0, remaining);
}

app.registerExtension({
    name: "promptgen.queueAllFiles",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODES.batchText) return;
        chain(nodeType, "onNodeCreated", function () {
            const button = this.addWidget("button", TITLE, null, () => queueAllFiles(this));
            button.serialize = false; // keeps the saved widget values unchanged
        });
    },
});
