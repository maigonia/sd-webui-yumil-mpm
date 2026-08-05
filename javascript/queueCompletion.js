(function () {
    "use strict";

    const core = globalThis.YumilMpmQueueCompletionCore;
    if (!core) {
        console.warn("[Yumil MPM] Queue completion support could not be loaded.");
        return;
    }
    const inFlight = new Set();
    const handledTasks = new Set();
    const tabs = ["txt2img", "img2img"];

    function generateForeverAdapter(tab) {
        if (tab === "txt2img") {
            if (typeof regen_txt2img === "undefined") return null;
            return {
                get: () => regen_txt2img,
                set: (value) => { regen_txt2img = value; },
            };
        }
        if (tab === "img2img") {
            if (typeof regen_img2img === "undefined") return null;
            return {
                get: () => regen_img2img,
                set: (value) => { regen_img2img = value; },
            };
        }
        return null;
    }

    function showCompletionNotice(tab, signal) {
        const generateBox = gradioApp().getElementById(`${tab}_generate_box`);
        if (!generateBox) return;

        const noticeId = `yumil_mpm_${tab}_queue_completion`;
        let notice = gradioApp().getElementById(noticeId);
        if (!notice) {
            notice = document.createElement("div");
            notice.id = noticeId;
            notice.style.margin = "0.4rem 0";
            notice.style.padding = "0.45rem 0.65rem";
            notice.style.border = "1px solid var(--border-color-primary)";
            notice.style.borderRadius = "var(--radius-md)";
            notice.style.background = "var(--background-fill-secondary)";
            generateBox.insertAdjacentElement("afterend", notice);
        }

        notice.textContent = signal.queue_state === "exhausted"
            ? "Yumil MPM: No queue remains. Automatic generation was stopped."
            : "Yumil MPM: Queue completed. Automatic generation was stopped.";
        notice.style.display = "block";
    }

    async function pollTask(tab, taskId) {
        if (!taskId || inFlight.has(taskId) || handledTasks.has(taskId)) return;
        inFlight.add(taskId);
        try {
            const response = await fetch("/yumil_mpm/queue-completion", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ task_id: taskId }),
            });
            if (!response.ok) return;

            const signal = core.readTerminalSignal(await response.json(), tab);
            if (!signal) return;

            handledTasks.add(taskId);
            if (handledTasks.size > 64) {
                handledTasks.delete(handledTasks.values().next().value);
            }

            const result = core.cancelGenerateForever(generateForeverAdapter(tab), clearInterval);
            if (!result.supported) {
                console.warn(`[Yumil MPM] Queue completed, but Forge Neo's ${tab} Generate forever handle is unavailable.`);
                return;
            }

            showCompletionNotice(tab, signal);
            console.info(`[Yumil MPM] Queue completed for ${tab}; automatic generation is stopped.`);
        } catch (error) {
            console.warn(`[Yumil MPM] Could not read queue completion state: ${error}`);
        } finally {
            inFlight.delete(taskId);
        }
    }

    function scanActiveTasks() {
        if (typeof localGet !== "function") return;
        for (const tab of tabs) {
            pollTask(tab, localGet(`${tab}_task_id`));
        }
    }

    onUiLoaded(function () {
        scanActiveTasks();
        setInterval(scanActiveTasks, 250);
    });
})();
