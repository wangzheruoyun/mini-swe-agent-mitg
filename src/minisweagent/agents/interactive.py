"""A small generalization of the default agent that puts the user in the loop.

There are three modes:
- human: commands issued by the user are executed immediately
- confirm: commands issued by the LM but not whitelisted are confirmed by the user
- yolo: commands issued by the LM are executed immediately without confirmation

Slash commands (available at most prompts via ``_prompt_and_handle_slash_commands``):
- /y  switch to yolo mode
- /c  switch to confirm mode
- /u  switch to human mode (rejects the current command when used at the
       confirmation prompt, or switches modes otherwise)
- /h  show the help text
- /m  enter a multiline comment (only at the top-level task prompt)
- /undo  revert the last executed action (InteractiveAgent only)
"""

import re
import sys
from typing import Literal, NoReturn

from rich.console import Console
from rich.rule import Rule

from minisweagent import i18n
from minisweagent.agents.default import AgentConfig, DefaultAgent
from minisweagent.agents.utils.prompt_user import _multiline_prompt, prompt_session
from minisweagent.exceptions import LimitsExceeded, Submitted, TimeExceeded, UndoRequested, UserInterruption
from minisweagent.models.utils.content_string import get_content_string

console = Console(highlight=False)
_ = i18n.t


class InteractiveAgentConfig(AgentConfig):
    mode: Literal["human", "confirm", "yolo"] = "confirm"
    """Whether to confirm actions."""
    whitelist_actions: list[str] = []
    """Never confirm actions that match these regular expressions."""
    confirm_exit: bool = True
    """If the agent wants to finish, do we ask for confirmation from user?"""
    undo_enabled: bool = True
    """Whether the user may undo the last executed action with /undo."""


class InteractiveAgent(DefaultAgent):
    _MODE_COMMANDS_MAPPING = {"/u": "human", "/c": "confirm", "/y": "yolo"}

    def __init__(self, *args, config_class=InteractiveAgentConfig, **kwargs):
        super().__init__(*args, config_class=config_class, **kwargs)
        self.cost_last_confirmed = 0.0
        # Index of the message list right before the current (in-flight) step's
        # assistant proposal was added. The most recent committed value doubles as
        # the checkpoint to truncate back to when the user requests /undo.
        self._step_start_index = 0
        self._pre_step_n_calls = 0
        self._pre_step_cost = 0.0
        self._undo_stack: list[tuple[int, int, float]] = []

    def _interrupt(self, content: str, *, itype: str = "UserInterruption") -> NoReturn:
        raise UserInterruption({"role": "user", "content": content, "extra": {"interrupt_type": itype}})

    def add_messages(self, *messages: dict) -> list[dict]:
        # Extend supermethod to print messages
        for msg in messages:
            role, content = msg.get("role") or msg.get("type", "unknown"), get_content_string(msg)
            if role == "assistant":
                console.print(
                    _("\n[red][bold]mini-swe-agent[/bold] (step [bold]{n_calls}[/bold], [bold]${cost:.2f}[/bold]):[/red]\n").format(
                        n_calls=self.n_calls, cost=self.cost
                    ),
                    end="",
                    highlight=False,
                )
            else:
                console.print(
                    _("\n[bold green]{role}[/bold green]:\n").format(role=str(role).capitalize()),
                    end="",
                    highlight=False,
                )
            console.print(content, highlight=False, markup=False)
        return super().add_messages(*messages)

    def query(self) -> dict:
        # Capture the checkpoint *before* this step starts (message index, step
        # count and cost) so a later /undo can revert this whole step cleanly,
        # including its accounting.
        self._step_start_index = len(self.messages)
        self._pre_step_n_calls = self.n_calls
        self._pre_step_cost = self.cost
        # Extend supermethod to handle human mode
        if self.config.mode == "human":
            match command := self._prompt_and_handle_slash_commands(_("[bold yellow]>[/bold yellow] ")):
                case "/y" | "/c":
                    pass
                case _:
                    msg = {
                        "role": "user",
                        "content": f"User command: \n```bash\n{command}\n```",
                        "extra": {"actions": [{"command": command}]},
                    }
                    self.add_messages(msg)
                    return msg
        try:
            with console.status(_("Waiting for the LM to respond...")):
                return super().query()
        except TimeExceeded:
            # A wall-clock limit can't be lifted by raising the step/cost limits
            # (the next query re-checks the clock and raises again), so prompting
            # would loop forever. Always stop cleanly instead.
            raise
        except LimitsExceeded:
            if not self._stdin_is_interactive():
                # No terminal to prompt for new limits -- e.g. an unattended
                # `--yolo` run, or any run with stdin redirected from /dev/null
                # (CI, a sandbox). Stop cleanly so the trajectory is saved with a
                # LimitsExceeded exit status, instead of crashing on EOFError when
                # reading input.
                raise
            console.print(
                _("Limits exceeded. Limits: {step_limit} steps, ${cost_limit}.\n"
                  "Current spend: {n_calls} steps, ${cost:.2f}.").format(
                    step_limit=self.config.step_limit,
                    cost_limit=self.config.cost_limit,
                    n_calls=self.n_calls,
                    cost=self.cost,
                )
            )
            self.config.step_limit = int(input(_("New step limit: ")))
            self.config.cost_limit = float(input(_("New cost limit: ")))
            return super().query()

    @staticmethod
    def _stdin_is_interactive() -> bool:
        """Whether an interactive terminal is available to prompt the user.

        Returns False for unattended runs (e.g. `--yolo` in CI, or inside a
        sandbox with stdin redirected from /dev/null), where calling ``input()``
        would raise ``EOFError`` and crash the run.
        """
        try:
            return sys.stdin is not None and sys.stdin.isatty()
        except (ValueError, OSError):
            return False

    def step(self) -> list[dict]:
        # Override the step method to handle user interruption and /undo.
        try:
            console.print(Rule())
            return super().step()
        except UndoRequested:
            # /undo was requested in the confirmation prompt. Revert the last
            # committed step in place and re-run this same step (re-prompting the
            # user) rather than bubbling up to the run loop. This keeps the
            # conversation consistent and lets the user issue a corrected command.
            self._undo_last_action()
            return self.step()
        except KeyboardInterrupt:
            interruption_message = self._prompt_and_handle_slash_commands(
                _("\n\n[bold yellow]Interrupted.[/bold yellow] "
                  "[green]Type a comment/command[/green] (/h for available commands)"
                  "\n[bold yellow]>[/bold yellow] ")
            ).strip()
            if not interruption_message or interruption_message in self._MODE_COMMANDS_MAPPING:
                interruption_message = _("Temporary interruption caught.")
            self._interrupt(_("Interrupted by user: {msg}").format(msg=interruption_message))

    def execute_actions(self, message: dict) -> list[dict]:
        # Override to handle user confirmation and confirm_exit, with try/finally to preserve partial outputs
        actions = message.get("extra", {}).get("actions", [])
        commands = [action["command"] for action in actions]
        outputs = []
        try:
            self._ask_confirmation_or_interrupt(commands)
            for action in actions:
                outputs.append(self.env.execute(action))
        except Submitted as e:
            self._check_for_new_task_or_submit(e)
        finally:
            result = self.add_messages(
                *self.model.format_observation_messages(message, outputs, self.get_template_vars())
            )
        # Commit: the step that started at _step_start_index has now executed,
        # so it becomes the checkpoint a future /undo will revert (along with the
        # step accounting captured before the step ran).
        self._undo_stack.append((self._step_start_index, self._pre_step_n_calls, self._pre_step_cost))
        return result

    def _undo_last_action(self) -> None:
        """Revert the most recently committed step.

        Truncates the message list back to the last checkpoint (which removes the
        step's assistant proposal and its observation) and rolls back the step
        counter and cost accrued by that step, so the run continues as if the
        step never happened. Triggered from ``step()`` when a ``/undo`` request
        is caught, which then re-runs the same step (re-prompting the user).
        """
        if not self._undo_stack:
            console.print(_("[bold yellow]Undo not available (no executed action to revert).[/bold yellow]"))
            return
        cut, prev_n_calls, prev_cost = self._undo_stack.pop()
        if cut < len(self.messages):
            del self.messages[cut:]
        self.n_calls = prev_n_calls
        self.cost = prev_cost
        console.print(_("[bold green]Undid last action.[/bold green]"))

    def _add_observation_messages(self, message: dict, outputs: list[dict]) -> list[dict]:
        return self.add_messages(*self.model.format_observation_messages(message, outputs, self.get_template_vars()))

    def _check_for_new_task_or_submit(self, e: Submitted) -> NoReturn:
        """Check if user wants to add a new task or submit."""
        if self.config.confirm_exit:
            message = (
                _("[bold yellow]Agent wants to finish.[/bold yellow] "
                  "[bold green]Type new task[/bold green] or [bold]Enter[/bold] to quit "
                  "([bold]/h[/bold] for commands)\n"
                  "[bold yellow]>[/bold yellow] ")
            )
            user_input = self._prompt_and_handle_slash_commands(message).strip()
            if user_input == "/u":  # directly continue
                self._interrupt("Switched to human mode.")
            elif user_input in self._MODE_COMMANDS_MAPPING:  # ask again
                return self._check_for_new_task_or_submit(e)
            elif user_input:
                self._interrupt(_("The user added a new task: {task}").format(task=user_input), itype="UserNewTask")
        raise e

    def _should_ask_confirmation(self, action: str) -> bool:
        return self.config.mode == "confirm" and not any(re.match(r, action) for r in self.config.whitelist_actions)

    def _ask_confirmation_or_interrupt(self, commands: list[str]) -> None:
        if not any(self._should_ask_confirmation(c) for c in commands):
            return
        prompt = (
            _("Execute {n} action(s)? [green][bold]Enter[/] to confirm[/], "
              "[red]type [bold]comment[/] to reject[/], or [blue][bold]/h[/] to show available commands\n"
              "[bold yellow]>[/bold yellow] ").format(n=len(commands))
        )
        match user_input := self._prompt_and_handle_slash_commands(prompt).strip():
            case "" | "/y":
                pass  # confirmed, do nothing
            case "/u":  # Skip execution action and get back to query
                self._interrupt("Commands not executed. Switching to human mode", itype="UserRejection")
            case _:
                self._interrupt(
                    _("Commands not executed. The user rejected your commands with the following message: {msg}").format(
                        msg=user_input
                    ),
                    itype="UserRejection",
                )

    def _prompt_and_handle_slash_commands(self, prompt: str, *, _multiline: bool = False) -> str:
        """Prompts the user, takes care of /h (followed by requery) and sets the mode. Returns the user input."""
        console.print(prompt, end="")
        if _multiline:
            return _multiline_prompt()
        user_input = prompt_session.prompt("")
        if user_input == "/m":
            return self._prompt_and_handle_slash_commands(prompt, _multiline=True)
        if user_input == "/h":
            console.print(
                _("Current mode: [bold green]{mode}[/bold green]\n"
                  "[bold green]/y[/bold green] to switch to [bold yellow]yolo[/bold yellow] mode (execute LM commands without confirmation)\n"
                  "[bold green]/c[/bold green] to switch to [bold yellow]confirmation[/bold yellow] mode (ask for confirmation before executing LM commands)\n"
                  "[bold green]/u[/bold green] to switch to [bold yellow]human[/bold yellow] mode (execute commands issued by the user)\n"
                  "[bold green]/m[/bold green] to enter multiline comment").format(mode=self.config.mode)
            )
            if self.config.undo_enabled:
                console.print(_("[bold green]/undo[/bold green] to undo the last executed action"))
            return self._prompt_and_handle_slash_commands(prompt)
        if user_input == "/undo":
            if not self.config.undo_enabled:
                return self._prompt_and_handle_slash_commands(prompt)
            if not self._undo_stack:
                console.print(_("[bold yellow]Undo not available (no executed action to revert).[/bold yellow]"))
                return self._prompt_and_handle_slash_commands(prompt)
            # Unwind to run()'s loop, which reverts the last committed step and
            # re-queries. Carrying a user message would corrupt the trajectory.
            raise UndoRequested({"role": "user", "content": "/undo", "extra": {"interrupt_type": "UndoRequested"}})
        if user_input in self._MODE_COMMANDS_MAPPING:
            if self.config.mode == self._MODE_COMMANDS_MAPPING[user_input]:
                return self._prompt_and_handle_slash_commands(
                    _("Already in {mode} mode.\n").format(mode=self.config.mode) + prompt
                )
            self.config.mode = self._MODE_COMMANDS_MAPPING[user_input]
            console.print(_("Switched to [bold green]{mode}[/bold green] mode.").format(mode=self.config.mode))
            return user_input
        return user_input
