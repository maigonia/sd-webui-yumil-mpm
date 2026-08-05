(function (root, factory) {
    const api = factory();
    root.YumilMpmQueueCompletionCore = api;
    if (typeof module === "object" && module.exports) {
        module.exports = api;
    }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
    "use strict";

    function readTerminalSignal(payload, expectedTab) {
        if (!payload || payload.terminal !== true || payload.should_continue !== false) {
            return null;
        }
        if (payload.tab !== expectedTab || !["txt2img", "img2img"].includes(payload.tab)) {
            return null;
        }
        return {
            should_continue: false,
            queue_state: typeof payload.queue_state === "string" ? payload.queue_state : null,
            stop_reason: typeof payload.stop_reason === "string" ? payload.stop_reason : null,
            tab: payload.tab,
        };
    }

    function cancelGenerateForever(adapter, clearTimer) {
        if (!adapter || typeof adapter.get !== "function" || typeof adapter.set !== "function") {
            return { supported: false, cancelled: false };
        }

        const handle = adapter.get();
        if (handle === null || typeof handle === "undefined") {
            return { supported: true, cancelled: false };
        }

        clearTimer(handle);
        adapter.set(null);
        return { supported: true, cancelled: true };
    }

    return { readTerminalSignal, cancelGenerateForever };
});
