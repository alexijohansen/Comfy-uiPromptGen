// PromptGen Template: keeps the numbered inputs ("1", "2", ...) growing.
// There is always exactly one free input at the end; connect it and a new one appears.
import { app } from "../../scripts/app.js";
import { NODES, chain, redraw } from "./common.js";

const LITEGRAPH_INPUT = 1;
const isListInput = (input) => input && !input.widget && /^\d+$/.test(input.name);

function normalizeInputs(node) {
    const listInputs = () => (node.inputs || []).filter(isListInput);

    // Remove trailing unconnected inputs, keeping one free at the end.
    let inputs = listInputs();
    while (inputs.length >= 2 && inputs.at(-1).link == null && inputs.at(-2).link == null) {
        node.removeInput(node.inputs.indexOf(inputs.at(-1)));
        inputs = listInputs();
    }

    // Make sure the last input is free.
    if (inputs.length === 0 || inputs.at(-1).link != null) {
        const next = inputs.length === 0 ? 1 : parseInt(inputs.at(-1).name, 10) + 1;
        node.addInput(String(next), "STRING");
    }

    node.setSize?.([node.size[0], Math.max(node.size[1], node.computeSize()[1])]);
    redraw(node);
}

app.registerExtension({
    name: "promptgen.templateInputs",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODES.template) return;

        chain(nodeType, "onNodeCreated", function () {
            normalizeInputs(this);
        });
        chain(nodeType, "onConfigure", function () {
            setTimeout(() => normalizeInputs(this), 0);
        });
        chain(nodeType, "onConnectionsChange", function (type) {
            // Deferred so LiteGraph finishes updating the link first; skipped while a workflow loads.
            if (type === LITEGRAPH_INPUT && !app.configuringGraph) setTimeout(() => normalizeInputs(this), 0);
        });
    },
});
