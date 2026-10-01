#!/usr/bin/env python3

"""Run mini-SWE-agent in your local environment. This is the default executable `mini`."""
# Read this first: https://mini-swe-agent.com/latest/usage/mini/  (usage)

import os
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from minisweagent import global_config_dir, i18n
from minisweagent.agents import get_agent
from minisweagent.agents.utils.prompt_user import _multiline_prompt
from minisweagent.config import builtin_config_dir, get_config_from_spec
from minisweagent.environments import get_environment
from minisweagent.models import get_model
from minisweagent.run.utilities.config import configure_if_first_time
from minisweagent.run.utilities.session import save_session
from minisweagent.run.utilities.startup import bootstrap, resume_prompt
from minisweagent.utils.serialize import UNSET, recursive_merge

DEFAULT_CONFIG_FILE = Path(os.getenv("MSWEA_MINI_CONFIG_PATH", builtin_config_dir / "mini.yaml"))
DEFAULT_OUTPUT_FILE = global_config_dir / "last_mini_run.traj.json"

_ = i18n.t

_HELP_TEXT = """Run mini-SWE-agent in your local environment.

[not dim]
More information about the usage: [bold green]https://mini-swe-agent.com/latest/usage/mini/[/bold green]
[/not dim]
"""

_CONFIG_SPEC_HELP_TEXT = """Path to config files, filenames, or key-value pairs.

[bold red]IMPORTANT:[/bold red] [red]If you set this option, the default config file will not be used.[/red]
So you need to explicitly set it e.g., with [bold green]-c mini.yaml <other options>[/bold green]

Multiple configs will be recursively merged.

Examples:

[bold red]-c model.model_kwargs.temperature=0[/bold red] [red]You forgot to add the default config file! See above.[/red]

[bold green]-c mini.yaml -c model.model_kwargs.temperature=0.5[/bold green]

[bold green]-c swebench.yaml agent.mode=yolo[/bold green]
"""

console = Console(highlight=False)
app = typer.Typer(rich_markup_mode="rich")


# fmt: off
@app.command(help=_HELP_TEXT)
def main(
    model_name: str | None = typer.Option(None, "-m", "--model", help="Model to use",),
    model_class: str | None = typer.Option(None, "--model-class", help="Model class to use (e.g., 'litellm' or 'minisweagent.models.litellm_model.LitellmModel')", rich_help_panel="Advanced"),
    agent_class: str | None = typer.Option(None, "--agent-class", help="Agent class to use (e.g., 'interactive' or 'minisweagent.agents.interactive.InteractiveAgent')", rich_help_panel="Advanced"),
    environment_class: str | None = typer.Option(None, "--environment-class", help="Environment class to use (e.g., 'local' or 'minisweagent.environments.local.LocalEnvironment')", rich_help_panel="Advanced"),
    task: str | None = typer.Option(None, "-t", "--task", help="Task/problem statement", show_default=False),
    yolo: bool = typer.Option(False, "-y", "--yolo", help="Run without confirmation"),
    cost_limit: float | None = typer.Option(None, "-l", "--cost-limit", help="Cost limit. Set to 0 to disable."),
    config_spec: list[str] = typer.Option([str(DEFAULT_CONFIG_FILE)], "-c", "--config", help=_CONFIG_SPEC_HELP_TEXT),
    output: Path | None = typer.Option(DEFAULT_OUTPUT_FILE, "-o", "--output", help="Output trajectory file"),
    exit_immediately: bool = typer.Option(False, "--exit-immediately", help="Exit immediately when the agent wants to finish instead of prompting.", rich_help_panel="Advanced"),
) -> Any:
    # fmt: on
    # Cross-cutting startup concerns (language, dynamic env, key fallback, banner).
    bootstrap()
    configure_if_first_time()

    # Record the session so a later invocation can resume an unfinished run.
    save_session(output)

    # Build the config from the command line arguments
    console.print(_("Building agent config from specs: [bold green]{config_spec}[/bold green]").format(config_spec=config_spec))
    configs = [get_config_from_spec(spec) for spec in config_spec]
    configs.append({
        "run": {
            "task": task or UNSET,
        },
        "agent": {
            "agent_class": agent_class or UNSET,
            "mode": "yolo" if yolo else UNSET,
            "cost_limit": cost_limit if cost_limit is not None else UNSET,
            "confirm_exit": False if exit_immediately else UNSET,
            "output_path": output or UNSET,
        },
        "model": {
            "model_class": model_class or UNSET,
            "model_name": model_name or UNSET,
        },
        "environment": {
            "environment_class": environment_class or UNSET,
        },
    })
    config = recursive_merge(*configs)

    model = get_model(config=config.get("model", {}))
    env = get_environment(config.get("environment", {}), default_type="local")

    # Without an explicit task, resume the last unfinished session directly from
    # its trajectory file (restoring the full conversation and continuing from
    # where it left off). Only when there is no resumable session do we ask the
    # user what they want to do and start a fresh run.
    if (run_task := config.get("run", {}).get("task", UNSET)) is UNSET:
        resumed_path = resume_prompt()
        if resumed_path is not None:
            console.print(_("Resuming last session from trajectory file."))
            agent = get_agent(model, env, config.get("agent", {}), default_type="interactive").resume(
                resumed_path, model, env
            )
            agent.run()
        else:
            console.print(_("[bold yellow]What do you want to do?[/bold yellow]"))
            run_task = _multiline_prompt()
            console.print(_("[bold green]Got that, thanks![/bold green]"))
            agent = get_agent(model, env, config.get("agent", {}), default_type="interactive")
            agent.run(run_task)
    else:
        agent = get_agent(model, env, config.get("agent", {}), default_type="interactive")
        agent.run(run_task)
    if (output_path := config.get("agent", {}).get("output_path")):
        console.print(_("Saved trajectory to [bold green]'{output_path}'[/bold green]").format(output_path=output_path))
    return agent


if __name__ == "__main__":
    app()
