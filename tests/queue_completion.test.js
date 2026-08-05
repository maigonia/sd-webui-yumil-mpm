const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const {
    readTerminalSignal,
    cancelGenerateForever,
} = require("../javascript/queueCompletion.core.js");


test("reads only an explicit matching terminal signal", () => {
    const signal = readTerminalSignal({
        terminal: true,
        should_continue: false,
        queue_state: "completed",
        stop_reason: "queue_completed",
        tab: "txt2img",
    }, "txt2img");

    assert.equal(signal.tab, "txt2img");
    assert.equal(readTerminalSignal({ terminal: true, should_continue: 0, tab: "txt2img" }, "txt2img"), null);
    assert.equal(readTerminalSignal({ terminal: true, should_continue: false, tab: "img2img" }, "txt2img"), null);
    assert.equal(readTerminalSignal({ terminal: false, should_continue: false, tab: "txt2img" }, "txt2img"), null);
});

test("cancels only the supplied Generate forever handle", () => {
    let handle = 42;
    const cleared = [];
    const result = cancelGenerateForever({
        get: () => handle,
        set: (value) => { handle = value; },
    }, (value) => cleared.push(value));

    assert.deepEqual(result, { supported: true, cancelled: true });
    assert.deepEqual(cleared, [42]);
    assert.equal(handle, null);
});

test("cancellation is idempotent when automatic generation is already off", () => {
    const result = cancelGenerateForever({
        get: () => null,
        set: () => assert.fail("must not update an inactive handle"),
    }, () => assert.fail("must not clear an inactive handle"));

    assert.deepEqual(result, { supported: true, cancelled: false });
});

test("unsupported frontend adapter fails safely", () => {
    assert.deepEqual(
        cancelGenerateForever(null, () => assert.fail("must not clear without an adapter")),
        { supported: false, cancelled: false },
    );
});

test("browser integration clears only the matching shared Forge interval", async () => {
    for (const tab of ["txt2img", "img2img"]) {
        const cleared = [];
        let uiLoaded;
        const generateBox = { insertAdjacentElement: () => {} };
        const context = vm.createContext({
            console: { info: () => {}, warn: () => {} },
            clearInterval: (handle) => cleared.push(handle),
            setInterval: () => 1,
            onUiLoaded: (callback) => { uiLoaded = callback; },
            localGet: (key) => key === `${tab}_task_id` ? `task(${tab})` : null,
            fetch: async () => ({
                ok: true,
                json: async () => ({
                    terminal: true,
                    should_continue: false,
                    queue_state: "completed",
                    stop_reason: "queue_completed",
                    tab,
                }),
            }),
            gradioApp: () => ({
                getElementById: (id) => id === `${tab}_generate_box` ? generateBox : null,
            }),
            document: {
                createElement: () => ({ style: {}, textContent: "" }),
            },
        });

        vm.runInContext(
            `let regen_txt2img = ${tab === "txt2img" ? 10 : "null"}; let regen_img2img = ${tab === "img2img" ? 20 : "null"};`,
            context,
        );
        const javascriptDir = path.resolve(__dirname, "../javascript");
        vm.runInContext(fs.readFileSync(path.join(javascriptDir, "queueCompletion.core.js"), "utf8"), context);
        vm.runInContext(fs.readFileSync(path.join(javascriptDir, "queueCompletion.js"), "utf8"), context);

        uiLoaded();
        await new Promise((resolve) => setImmediate(resolve));

        assert.deepEqual(cleared, [tab === "txt2img" ? 10 : 20]);
        assert.equal(vm.runInContext("regen_txt2img", context), null);
        assert.equal(vm.runInContext("regen_img2img", context), null);
    }
});
