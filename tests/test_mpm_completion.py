import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "Scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from mpm_completion import (  # noqa: E402
    PROCESSING_COMPLETION_ID_ATTR,
    QUEUE_COMPLETION_ROUTE,
    TerminalSignalRegistry,
    attach_completion_id,
    finalize_processing,
    is_valid_completion_id,
    notify_mpm_finalization,
    parse_generation_response,
    register_completion_route,
)


COMPLETION_ID = f"cmp-{'a' * 32}"


class ParseGenerationResponseTests(unittest.TestCase):
    def test_active_response_preserves_prompts_without_terminal_signal(self):
        parsed = parse_generation_response({
            "results": [
                {"category_name": "Positive", "prompt": "cat", "success": True},
                {"category_name": "Positive", "prompt": "later duplicate", "success": True},
                {"category_name": "Negative", "prompt": "blur", "success": False},
            ],
            "should_continue": True,
            "queue_state": "active",
        })

        self.assertEqual(parsed.prompt_lookup, {"Positive": "cat"})
        self.assertIsNone(parsed.terminal_signal)
        self.assertIsNone(parsed.completion_id)

    def test_terminal_response_preserves_final_prompt_and_acknowledgement(self):
        parsed = parse_generation_response({
            "results": [
                {"category_name": "Positive", "prompt": "final", "success": True},
            ],
            "should_continue": False,
            "queue_state": "completed",
            "stop_reason": "queue_completed",
            "completion_ack_required": True,
            "completion_id": COMPLETION_ID,
        })

        self.assertEqual(parsed.prompt_lookup["Positive"], "final")
        self.assertEqual(parsed.terminal_signal, {
            "should_continue": False,
            "queue_state": "completed",
            "stop_reason": "queue_completed",
        })
        self.assertEqual(parsed.completion_id, COMPLETION_ID)

    def test_exhausted_response_stops_without_acknowledgement(self):
        parsed = parse_generation_response({
            "results": [],
            "should_continue": False,
            "queue_state": "exhausted",
            "stop_reason": "no_queue",
            "completion_ack_required": True,
            "completion_id": COMPLETION_ID,
        })

        self.assertEqual(parsed.prompt_lookup, {})
        self.assertEqual(parsed.terminal_signal["queue_state"], "exhausted")
        self.assertIsNone(parsed.completion_id)

    def test_missing_or_non_boolean_stop_signal_preserves_legacy_behavior(self):
        for should_continue in (None, 0, "false"):
            with self.subTest(should_continue=should_continue):
                parsed = parse_generation_response({
                    "results": [],
                    "should_continue": should_continue,
                })
                self.assertIsNone(parsed.terminal_signal)

    def test_malformed_optional_metadata_is_sanitized(self):
        parsed = parse_generation_response({
            "results": "invalid",
            "should_continue": False,
            "queue_state": "unknown",
            "stop_reason": 123,
            "completion_ack_required": True,
            "completion_id": "bad",
        })

        self.assertEqual(parsed.prompt_lookup, {})
        self.assertEqual(parsed.terminal_signal["queue_state"], None)
        self.assertEqual(parsed.terminal_signal["stop_reason"], None)
        self.assertIsNone(parsed.completion_id)


class TerminalSignalRegistryTests(unittest.TestCase):
    def test_signal_is_isolated_by_task_and_consumed_once(self):
        registry = TerminalSignalRegistry()
        signal = {
            "should_continue": False,
            "queue_state": "completed",
            "stop_reason": "queue_completed",
            "completion_id": COMPLETION_ID,
        }

        self.assertTrue(registry.record("task(one)", "txt2img", signal))
        self.assertIsNone(registry.take("task(other)"))
        result = registry.take("task(one)")
        self.assertEqual(result["tab"], "txt2img")
        self.assertNotIn("completion_id", result)
        self.assertIsNone(registry.take("task(one)"))

    def test_signal_expires(self):
        now = [10.0]
        registry = TerminalSignalRegistry(ttl_seconds=5, clock=lambda: now[0])
        registry.record(
            "task(expiring)",
            "img2img",
            {"should_continue": False, "queue_state": "completed", "stop_reason": "queue_completed"},
        )
        now[0] = 15.0
        self.assertIsNone(registry.take("task(expiring)"))

    def test_capacity_evicts_only_the_oldest_entry_on_record(self):
        registry = TerminalSignalRegistry(max_entries=2)
        signal = {"should_continue": False, "queue_state": "completed", "stop_reason": "queue_completed"}
        registry.record("task(first)", "txt2img", signal)
        registry.record("task(second)", "txt2img", signal)

        self.assertIsNotNone(registry.take("task(first)"))
        registry.record("task(first)", "txt2img", signal)
        registry.record("task(third)", "txt2img", signal)

        self.assertIsNone(registry.take("task(second)"))
        self.assertIsNotNone(registry.take("task(first)"))
        self.assertIsNotNone(registry.take("task(third)"))

    def test_invalid_task_or_non_terminal_signal_is_rejected(self):
        registry = TerminalSignalRegistry()
        self.assertFalse(registry.record("bad", "txt2img", {"should_continue": False}))
        self.assertFalse(registry.record("task(ok)", "other", {"should_continue": False}))
        self.assertFalse(registry.record("task(ok)", "txt2img", {"should_continue": True}))

    def test_route_registration_is_idempotent(self):
        app = SimpleNamespace(routes=[])

        def add_api_route(path, endpoint, methods, name):
            app.routes.append(SimpleNamespace(
                path=path,
                endpoint=endpoint,
                methods=methods,
                name=name,
            ))

        app.add_api_route = add_api_route
        register_completion_route(None, app)
        register_completion_route(None, app)

        self.assertEqual(len(app.routes), 1)
        self.assertEqual(app.routes[0].path, QUEUE_COMPLETION_ROUTE)


class FinalizationTests(unittest.TestCase):
    def test_completion_id_validation(self):
        self.assertTrue(is_valid_completion_id(COMPLETION_ID))
        self.assertFalse(is_valid_completion_id("cmp-short"))
        self.assertFalse(is_valid_completion_id(f"cmp-{'z' * 32}"))

    def test_processing_is_acknowledged_once(self):
        processing = SimpleNamespace()
        notifier = Mock()
        self.assertTrue(attach_completion_id(processing, COMPLETION_ID))

        self.assertTrue(finalize_processing(processing, notifier))
        self.assertFalse(finalize_processing(processing, notifier))
        notifier.assert_called_once_with(COMPLETION_ID)
        self.assertIsNone(getattr(processing, PROCESSING_COMPLETION_ID_ATTR))

    def test_failed_notification_is_not_retried_implicitly(self):
        processing = SimpleNamespace()
        attach_completion_id(processing, COMPLETION_ID)
        notifier = Mock(side_effect=RuntimeError("offline"))

        with self.assertRaisesRegex(RuntimeError, "offline"):
            finalize_processing(processing, notifier)
        self.assertFalse(finalize_processing(processing, notifier))

    @patch("mpm_completion.load_api_key", return_value="secret")
    @patch("mpm_completion.requests.post")
    def test_authenticated_success_notification(self, post, _load_key):
        response = Mock()
        response.json.return_value = {"result": "accepted"}
        post.return_value = response

        result = notify_mpm_finalization(COMPLETION_ID)

        self.assertEqual(result, {"result": "accepted"})
        post.assert_called_once_with(
            "http://127.0.0.1:19720/api/v1/generation/finalized",
            headers={
                "Authorization": "Bearer secret",
                "Content-Type": "application/json",
            },
            json={"completion_id": COMPLETION_ID, "status": "succeeded"},
            timeout=15,
        )
        response.raise_for_status.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
