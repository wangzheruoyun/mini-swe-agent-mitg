"""Tests for the /undo (revert last executed action) feature of InteractiveAgent."""

from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

from minisweagent.agents.interactive import InteractiveAgent
from minisweagent.environments.local import LocalEnvironment
from minisweagent.exceptions import UndoRequested
from minisweagent.models.test_models import (
    DeterministicToolcallModel,
    make_toolcall_output,
)


@pytest.fixture
def toolcall_config():
    config_path = Path("src/minisweagent/config/mini.yaml")
    return yaml.safe_load(config_path.read_text())["agent"]


def _tc_model(specs):
    outputs = []
    for i, (content, actions) in enumerate(specs):
        tool_calls = []
        tc_actions = []
        for j, action in enumerate(actions):
            tc_id = f"call_{i}_{j}"
            tc_actions.append({"command": action["command"], "tool_call_id": tc_id})
            tool_calls.append(
                {
                    "id": tc_id,
                    "type": "function",
                    "function": {"name": "bash", "arguments": f'{{"command": "{action["command"]}"}}'},
                }
            )
        outputs.append(make_toolcall_output(content, tool_calls, tc_actions))
    return DeterministicToolcallModel(outputs=outputs)


def test_undo_last_action_reverts_committed_step(toolcall_config):
    agent = InteractiveAgent(
        Mock(), LocalEnvironment(), **{**toolcall_config, "mode": "yolo", "confirm_exit": False}
    )
    agent.messages = [
        {"role": "system"},
        {"role": "user"},
        {"role": "assistant"},
        {"role": "tool"},
    ]
    agent._undo_stack = [(1, 1, 0.0)]
    agent.n_calls = 2
    agent.cost = 0.5
    agent._undo_last_action()
    assert agent.messages == [{"role": "system"}]
    assert agent.n_calls == 1
    assert agent.cost == 0.0
    assert agent._undo_stack == []


def test_undo_with_empty_stack_is_safe_noop(toolcall_config):
    agent = InteractiveAgent(
        Mock(), LocalEnvironment(), **{**toolcall_config, "mode": "yolo", "confirm_exit": False}
    )
    agent.messages = [{"role": "a"}, {"role": "b"}]
    agent._undo_stack = []
    agent.n_calls = 1
    agent._undo_last_action()
    assert agent.messages == [{"role": "a"}, {"role": "b"}]
    assert agent.n_calls == 1


def test_undo_during_confirm_reverts_previous_step_and_continues(toolcall_config):
    from contextlib import contextmanager

    from tests.agents.test_interactive import mock_prompts

    model = _tc_model(
        [
            ("Step 1", [{"command": "echo step1"}]),
            ("Step 2", [{"command": "echo step2"}]),
            ("Step 3", [{"command": "echo step3"}]),
            ("Finishing", [{"command": "echo 'COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT'\necho done"}]),
        ]
    )
    with mock_prompts(["", "/undo", "", "", ""]):
        agent = InteractiveAgent(
            model=model,
            env=LocalEnvironment(),
            **{**toolcall_config, "mode": "confirm", "confirm_exit": False, "cost_limit": 100.0, "step_limit": 100},
        )
        info = agent.run("Undo test")
    # The run should still complete after undoing step 1.
    assert info["submission"] == "done\n"
    # The undone step's command must not appear in the final messages.
    all_content = " ".join(str(m.get("content", "")) for m in agent.messages)
    assert "step1" not in all_content
    # But the later steps survived.
    assert "step3" in all_content
