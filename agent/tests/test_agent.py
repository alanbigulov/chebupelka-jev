"""Offline checks of the original agent with synthetic API responses."""

from contextlib import redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch


AGENT_DIR = Path(__file__).resolve().parents[1]
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class AgentLoopTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            "test_target_agent", AGENT_DIR / "chebupelkajev.py"
        )
        self.agent = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "synthetic-test-key"}):
            spec.loader.exec_module(self.agent)
        self.sent_requests = []
        self.output = io.StringIO()

    def fake_post(self, responses):
        def post(url, *, json, headers):
            # The loop later mutates messages, so retain each request as sent.
            self.sent_requests.append(deepcopy({"url": url, "json": json}))
            response = Mock()
            response.json.return_value = responses[len(self.sent_requests) - 1]
            return response

        return post

    def load_fixture(self, name):
        return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))

    def initial_messages(self, prompt):
        return [
            {"role": "system", "content": self.agent.SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

    def test_text_response_finishes_without_tools(self):
        response = self.load_fixture("text_response.json")
        prompt = "Ответь текстом и заверши работу."
        with (
            patch.object(self.agent.requests, "post", side_effect=self.fake_post([response])) as post,
            patch.object(self.agent, "call_tool") as call_tool,
            redirect_stdout(self.output),
        ):
            self.agent.agent_loop(prompt)

        post.assert_called_once()
        call_tool.assert_not_called()
        self.assertEqual(self.sent_requests[0]["json"]["messages"], self.initial_messages(prompt))
        self.assertEqual(self.sent_requests[0]["json"]["thinking"], {"type": "disabled"})
        self.assertIn(response["choices"][0]["message"]["content"], self.output.getvalue())
        self.assertIn("Agent finished", self.output.getvalue())

    def test_pwd_result_and_call_id_are_forwarded_before_final_answer(self):
        responses = self.load_fixture("pwd_tool_cycle.json")
        prompt = "Выполни pwd один раз, затем заверши работу."
        real_run = subprocess.run
        command_results = []

        def bounded_pwd(command, **options):
            self.assertEqual(command, "pwd")
            result = real_run(["pwd"], capture_output=True, text=True, timeout=5)
            command_results.append(result)
            return result

        with (
            patch.object(self.agent.requests, "post", side_effect=self.fake_post(responses)) as post,
            patch.object(self.agent.subprocess, "run", side_effect=bounded_pwd) as run,
            redirect_stdout(self.output),
        ):
            self.agent.agent_loop(prompt)

        self.assertEqual(post.call_count, 2)
        run.assert_called_once()
        result = command_results[0]
        self.assertEqual(result.returncode, 0)
        self.assertEqual(Path(result.stdout.strip()).resolve(), Path.cwd().resolve())
        self.assertEqual(result.stderr, "")
        tool_message = responses[0]["choices"][0]["message"]
        tool_call = tool_message["tool_calls"][0]
        expected_history = self.initial_messages(prompt) + [
            {
                "role": "assistant",
                "content": tool_message["content"],
                "tool_calls": [tool_call],
            },
            {
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": f"Exit code: 0\n{result.stdout}",
            },
        ]
        self.assertEqual(self.sent_requests[0]["json"]["messages"], self.initial_messages(prompt))
        self.assertEqual(self.sent_requests[1]["json"]["messages"], expected_history)
        self.assertIn(responses[1]["choices"][0]["message"]["content"], self.output.getvalue())
        self.assertIn("Agent finished", self.output.getvalue())


if __name__ == "__main__":
    unittest.main()
