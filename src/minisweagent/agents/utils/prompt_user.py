from prompt_toolkit.formatted_text.html import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.shortcuts import PromptSession

from minisweagent import global_config_dir
from minisweagent import i18n

_history = FileHistory(global_config_dir / "interactive_history.txt")
prompt_session = PromptSession(history=_history)
_multiline_prompt_session = PromptSession(history=_history, multiline=True)


def _multiline_prompt() -> str:
    return _multiline_prompt_session.prompt(
        "",
        bottom_toolbar=HTML(
            i18n.t(
                "Submit message: [b fg='yellow' bg='black']Esc, then Enter[/b] | "
                "Navigate history: [b fg='yellow' bg='black']Arrow Up/Down[/b] | "
                "Search history: [b fg='yellow' bg='black']Ctrl+R[/b]"
            )
        ),
    )
