import copy
import hashlib
import unittest

import test_native_dispatch as fixtures


class ClaudeDispatchTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.NativeDispatchTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.state["assignments"][0]["requested"]["transport"] = "claude-cli"

    def render(self):
        return fixtures.backend.render_dispatch(self.f.engine, self.f.args, self.f.state, "claude-cli")

    def test_identity_bound_result_is_read_only(self):
        before = fixtures.inventory(self.f.root)
        result = self.render()
        self.assertEqual(result["message_sha256"], hashlib.sha256(result["message"].encode()).hexdigest())
        self.assertEqual(result["packet"], self.f.packet_id)
        self.assertEqual(result["artifact"], self.f.artifact)
        self.assertEqual(result["requested"]["transport"], "claude-cli")
        self.assertEqual(result["final_output"]["template"]["packet"], self.f.packet_id)
        self.assertEqual(result["final_output"]["template"]["assignment"], "review-1")
        self.assertFalse(result["writes"])
        self.assertEqual(result["dispatch"], "none")
        self.assertNotIn("task_name", result)
        self.assertIn("original µ frozen source\n", result["message"])
        self.assertEqual(result["message"].count("# Frozen collaboration context"), 1)
        self.assertEqual(fixtures.inventory(self.f.root), before)

    def test_unsupported_or_stale_state_is_refused(self):
        initial = self.f.state
        before = fixtures.inventory(self.f.root)
        for change in (
            lambda a, s: a["spec"].update(role="writer"),
            lambda a, s: a["requested"].update(transport="codex-native"),
            lambda a, s: a.update(continuation={"partial_work": "required"}),
            lambda a, s: a["observations"][0]["receipt"].update(invocation="already-started"),
            lambda a, s: s.update(current_artifact="0" * 64),
        ):
            state = self.f.state = copy.deepcopy(initial)
            change(state["assignments"][0], state)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.render()
            self.assertEqual(fixtures.inventory(self.f.root), before)
