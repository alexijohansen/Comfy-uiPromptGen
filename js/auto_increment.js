// Counter and the batch loaders: with auto_increment on, the number field goes up by 1 each time
// the workflow is queued, so the field always shows the next number. The backend counts too
// (promptgen/core/counting.py), so batches get 1, 2, 3 ... even if the UI doesn't update.
import { app } from "../../scripts/app.js";
import { NODES, chain, getWidget, redraw } from "./common.js";

// node ID -> the INT widget that counts up
const COUNTING_WIDGET = {
    [NODES.counter]: "current_number",
    [NODES.batchText]: "index",
    [NODES.batchImage]: "index",
    [NODES.batchVideo]: "index",
};

function setNumber(node, widget, value) {
    widget.value = value;
    widget.callback?.(value);
    redraw(node);
}

app.registerExtension({
    name: "promptgen.autoIncrement",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        const widgetName = COUNTING_WIDGET[nodeData.name];
        if (!widgetName) return;

        chain(nodeType, "onNodeCreated", function () {
            const node = this;
            const numberWidget = getWidget(node, widgetName);
            if (!numberWidget) return;
            // Called by the frontend right after each queued run was sent with the current value.
            const previous = numberWidget.afterQueued;
            numberWidget.afterQueued = function () {
                previous?.apply(this, arguments);
                if (getWidget(node, "auto_increment")?.value !== false) {
                    setNumber(node, numberWidget, Number(numberWidget.value) + 1);
                }
            };
        });

        // After a run, make sure the field shows at least the next number.
        chain(nodeType, "onExecuted", function (message) {
            const next = Number(message?.next_number?.[0]);
            const widget = getWidget(this, widgetName);
            if (widget && Number.isFinite(next) && next > Number(widget.value)) setNumber(this, widget, next);
        });
    },
});
