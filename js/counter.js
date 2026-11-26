import { app } from "../../scripts/app.js";

// PromptGen Counter / Batch Text Loader: current_number / index goes up by 1 each time the workflow is queued
// (when auto_increment is on), so batches get 1, 2, 3 ... and the field always shows the next number.

function getWidget(node, name) {
    return node.widgets?.find((w) => w.name === name);
}

// node type -> the INT widget that counts up
const COUNTING_WIDGET = {
    PromptGenCounter: "current_number",
    PromptGenBatchText: "index",
};

function setNumber(node, value) {
    const w = getWidget(node, node._promptgenCountWidget);
    if (!w) return;
    w.value = value;
    w.callback?.(value);
    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

app.registerExtension({
    name: "promptgen.counter",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        const widgetName = COUNTING_WIDGET[nodeData.name];
        if (!widgetName) return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated?.apply(this, arguments);
            const node = this;
            node._promptgenCountWidget = widgetName;
            const numberWidget = getWidget(node, widgetName);
            if (numberWidget) {
                // Called by the frontend right after the prompt (with the current value) was queued.
                const prev = numberWidget.afterQueued;
                numberWidget.afterQueued = function () {
                    prev?.apply(this, arguments);
                    if (getWidget(node, "auto_increment")?.value !== false) {
                        setNumber(node, Number(numberWidget.value) + 1);
                    }
                };
            }
            return r;
        };

        // Fallback for frontends that don't call afterQueued: after the node runs,
        // make sure the field shows at least the next number.
        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            onExecuted?.apply(this, arguments);
            const next = Number(message?.next_number?.[0]);
            const w = getWidget(this, widgetName);
            if (w && Number.isFinite(next) && next > Number(w.value)) setNumber(this, next);
        };
    },
});
