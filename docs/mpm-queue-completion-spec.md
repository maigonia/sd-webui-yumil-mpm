# MPM Queue Completion Integration for Forge Neo

## Goal

Consume Yumil MPM's additive generation-continuation fields so Forge Neo uses
the final finite-queue prompt, finishes image generation and saving, and then
stops only the browser's next `Generate forever` execution.

When MPM supplies a one-time completion ID, acknowledge success only after
Forge Neo's processing pipeline, including configured output saves, completes.

## Response Contract

The extension continues to read `results` from `POST /api/v1/generate` as it
does today. The following fields are optional and additive:

- `should_continue`: authoritative only when it is a JSON boolean.
- `queue_state`: accepted values are `active`, `completed`, and `exhausted`.
- `stop_reason`: accepted values are `queue_completed` and `no_queue`.
- `completion_ack_required`: authoritative only when it is exactly `true`.
- `completion_id`: accepted only as `cmp-` followed by 32 hexadecimal digits.

Missing or malformed optional fields preserve the existing behavior. Network
errors, HTTP errors, timeouts, and invalid JSON are not completion signals.

## Final-Prompt Behavior

A terminal response may still contain successful prompt results. The extension
must apply those prompts and reference-image blocks normally. It must not
interrupt the active generation, click Forge's Interrupt button, clear queued
work, or disable the External Prompt Requester.

Only an explicit JSON `should_continue: false` creates a terminal stop signal.

## Task-Scoped Browser Bridge

Forge Neo implements `Generate forever` in browser JavaScript with independent
`regen_txt2img` and `regen_img2img` interval handles. The Python generation
callback runs under a Gradio task ID exposed as `shared.state.job`; the same
browser stores that ID as `txt2img_task_id` or `img2img_task_id`.

1. Python records a sanitized terminal signal keyed by the current task ID and
   tab (`txt2img` or `img2img`).
2. A bounded runtime-only registry expires stale entries and never stores API
   bearer tokens.
3. A same-origin extension endpoint accepts the current browser task ID and
   returns only its sanitized terminal signal, if present.
4. Extension JavaScript polls only while a Forge task is active.
5. On a matching terminal signal, JavaScript clears only the corresponding
   `regen_txt2img` or `regen_img2img` interval and sets that handle to `null`.
6. The operation is idempotent. Manual Generate remains available.

If a supported Generate-forever handle is unavailable, the extension logs a
warning and leaves the active job untouched. It must not fall back to brittle
button-text matching or an Interrupt click.

## Finalization Acknowledgement

For a terminal `completed` / `queue_completed` response, Python stores a valid
completion ID on the current Forge processing object only when
`completion_ack_required` is exactly `true` and the terminal response is bound
to a valid Forge browser task. An arbitrary external API loop is not
acknowledged because the extension cannot prove that controller has stopped.

Forge Neo invokes an always-visible script's `postprocess` after its configured
sample, mask, grid, and video save operations. At that point the extension sends
an authenticated request to:

```text
POST /api/v1/generation/finalized
{"completion_id":"cmp-...","status":"succeeded"}
```

The existing `~/.mpm/api_key` / `MPM_API_KEY` loading path is reused. The ID is
cleared before the network call so duplicate postprocessing cannot acknowledge
twice.

If generation raises before `postprocess`, the ID is absent or malformed, or
the finalization request fails, the extension never reports success. MPM stays
in its safe `awaiting_external_completion` state and does not sleep.

## Compatibility and Scope

- Older MPM versions omit the fields and retain current Forge behavior.
- Normal `should_continue: true` responses do not create browser state.
- Terminal signals are isolated by task ID and tab rather than a process-global
  completion flag.
- The browser receives neither the bearer token nor the completion ID.
- The built-in Forge Neo browser `Generate forever` loop is supported.
- Arbitrary third-party clients repeatedly calling Forge's API must stop their
  own request loops; the extension cannot cancel an external controller.

## Verification

- Python tests: active, terminal-with-prompts, exhausted, legacy, malformed,
  transport/HTTP/JSON failure, task isolation/expiry, completion-ID validation,
  and one-time postprocess acknowledgement.
- JavaScript tests: txt2img/img2img cancellation, idempotency, unrelated task
  isolation, and unsupported frontend behavior.
- Static checks: Python compilation/import boundary, README encoding, and
  `git diff --check`.
- GPU acceptance later: finite queue, final image saved, no next MPM request,
  manual Generate still usable, and optional MPM sleep countdown begins only
  after finalization.
