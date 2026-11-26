import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// "Queue all files" button on PromptGen Batch Text Loader:
// counts the .txt files left in the folder and queues that many runs.

function notify(severity, summary, detail) {
    const toast = app.extensionManager?.toast;
    if (toast?.add) toast.add({ severity, summary, detail, life: 5000 });
    else console[severity === "error" ? "error" : "log"](`[PromptGen] ${summary}: ${detail}`);
}

app.registerExtension({
    name: "promptgen.batchText",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "PromptGenBatchText") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated?.apply(this, arguments);
            const node = this;
            const get = (name) => node.widgets?.find((w) => w.name === name);

            const button = node.addWidget("button", "Queue all files", null, async () => {
                const folder = get("folder")?.value ?? "";
                const index = Number(get("index")?.value ?? 0);
                if (get("auto_increment")?.value === false) {
                    notify("warn", "Queue all files", "Turn auto_increment on first, or every run loads the same file.");
                    return;
                }
                let data;
                try {
                    const res = await api.fetchApi(`/promptgen/count_files?folder=${encodeURIComponent(folder)}`);
                    data = await res.json();
                } catch (e) {
                    notify("error", "Queue all files", String(e));
                    return;
                }
                if (data.error) {
                    notify("error", "Queue all files", data.error);
                    return;
                }
                const remaining = get("when_done")?.value === "start over" ? data.total : data.total - index;
                if (remaining <= 0) {
                    notify("warn", "Queue all files", `All ${data.total} files are done. Set index back to 0 to start again.`);
                    return;
                }
                notify("info", "Queue all files", `Queueing ${remaining} run(s), files ${index + 1}-${index + remaining} of ${data.total}.`);
                await app.queuePrompt(0, remaining);
            });
            button.serialize = false; // keep saved widget values unchanged
            return r;
        };
    },
});
