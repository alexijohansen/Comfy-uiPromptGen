import { app } from "../../scripts/app.js";

// Keeps the PromptGen Template node's numbered inputs ("1", "2", ...) growing:
// there is always exactly one free slot at the end. Connect it and a new one appears.

const isListSlot = (input) => input && !input.widget && /^\d+$/.test(input.name);

function normalizeInputs(node) {
    let slots = () => (node.inputs || []).filter(isListSlot);

    // Remove trailing unconnected slots, keeping one free at the end.
    let list = slots();
    while (list.length >= 2 && list[list.length - 1].link == null && list[list.length - 2].link == null) {
        node.removeInput(node.inputs.indexOf(list[list.length - 1]));
        list = slots();
    }

    // Make sure the last slot is free.
    if (list.length === 0 || list[list.length - 1].link != null) {
        const next = list.length === 0 ? 1 : parseInt(list[list.length - 1].name, 10) + 1;
        node.addInput(String(next), "STRING");
    }

    node.setSize?.([node.size[0], Math.max(node.size[1], node.computeSize()[1])]);
    node.setDirtyCanvas?.(true, true);
}

app.registerExtension({
    name: "promptgen.template.dynamicInputs",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "PromptGenTemplate") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated?.apply(this, arguments);
            normalizeInputs(this);
            return r;
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const r = onConfigure?.apply(this, arguments);
            setTimeout(() => normalizeInputs(this), 0);
            return r;
        };

        const onConnectionsChange = nodeType.prototype.onConnectionsChange;
        nodeType.prototype.onConnectionsChange = function (type, index, connected, linkInfo) {
            const r = onConnectionsChange?.apply(this, arguments);
            if (type === 1 /* LiteGraph.INPUT */ && !app.configuringGraph) {
                // Defer so LiteGraph finishes updating the link first.
                setTimeout(() => normalizeInputs(this), 0);
            }
            return r;
        };
    },
});
