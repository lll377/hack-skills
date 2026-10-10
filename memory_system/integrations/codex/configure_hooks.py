from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = Path(__file__).resolve().parent
PYTHON = (ROOT / ".venv" / "Scripts" / "python.exe").resolve()

# Codex Hook 外层超时时间。
# memory_system/integrations/codex/settings.json 中的
# request_timeout_seconds 为 60 秒，因此这里预留10秒设为70秒。
HOOK_TIMEOUT = 70

COMMANDS = {
    "hook_session_start.cmd": ("SessionStart", HOOK_TIMEOUT),
    "hook_user_prompt.cmd": ("UserPromptSubmit", HOOK_TIMEOUT),
    "hook_post_tool_use.cmd": ("PostToolUse", HOOK_TIMEOUT),
    "hook_stop.cmd": ("Stop", HOOK_TIMEOUT),
    "hook_pre_compact.cmd": ("PreCompact", HOOK_TIMEOUT),
    "hook_session_end.cmd": ("SessionEnd", HOOK_TIMEOUT),
}


def command_entry(
    name: str,
    timeout: int,
    status: str,
    context_limit: int | None = None,
) -> dict:
    path = str((DIRECTORY / name).resolve())

    data = {
        "type": "command",
        "command": path,
        "commandWindows": path,
        "timeout": timeout,
        "statusMessage": status,
    }

    if context_limit is not None:
        data["additionalContextLimit"] = context_limit

    return data


def build() -> dict:
    return {
        "description": (
            "Project-local six-stage Codex context lifecycle backed by "
            "memory_system at 127.0.0.1:8765."
        ),
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "^(startup|resume|compact)$",
                    "hooks": [
                        command_entry(
                            "hook_session_start.cmd",
                            HOOK_TIMEOUT,
                            "Restoring bounded task context",
                            5000,
                        )
                    ],
                }
            ],
            "UserPromptSubmit": [
                {
                    "hooks": [
                        command_entry(
                            "hook_user_prompt.cmd",
                            HOOK_TIMEOUT,
                            "Saving prompt and recalling relevant context",
                            5000,
                        )
                    ]
                }
            ],
            "PostToolUse": [
                {
                    "hooks": [
                        command_entry(
                            "hook_post_tool_use.cmd",
                            HOOK_TIMEOUT,
                            "Saving structured tool progress",
                        )
                    ]
                }
            ],
            "Stop": [
                {
                    "hooks": [
                        command_entry(
                            "hook_stop.cmd",
                            HOOK_TIMEOUT,
                            "Saving structured checkpoint",
                        )
                    ]
                }
            ],
            "PreCompact": [
                {
                    "hooks": [
                        command_entry(
                            "hook_pre_compact.cmd",
                            HOOK_TIMEOUT,
                            "Saving task context anchor",
                        )
                    ]
                }
            ],
            "SessionEnd": [
                {
                    "hooks": [
                        command_entry(
                            "hook_session_end.cmd",
                            HOOK_TIMEOUT,
                            "Saving final recovery position",
                        )
                    ]
                }
            ],
        },
    }


def main() -> int:
    if not PYTHON.is_file():
        raise SystemExit(f"formal venv python missing: {PYTHON}")

    for name, (event, _) in COMMANDS.items():
        script = (DIRECTORY / "context_hook.py").resolve()
        command = f'"{PYTHON}" "{script}" --event {event}'

        content = (
            "@echo off\r\n"
            "chcp 65001 >nul\r\n"
            "set PYTHONUTF8=1\r\n"
            "set PYTHONIOENCODING=utf-8\r\n"
            + command
            + "\r\n"
            "exit /b %ERRORLEVEL%\r\n"
        )

        (DIRECTORY / name).write_text(content, encoding="ascii")

    obsolete = DIRECTORY / "hook_capture_prompt.cmd"
    if obsolete.exists():
        obsolete.unlink()

    target = ROOT / ".codex" / "hooks.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(build(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    project_config = ROOT / ".codex" / "config.toml"
    project_config.write_text(
        'project_root_markers = [".git", ".codex"]\n\n'
        "[features]\n"
        "hooks = true\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "hooks": str(target),
                "commands": sorted(COMMANDS),
                "python": str(PYTHON),
                "hook_timeout_seconds": HOOK_TIMEOUT,
            },
            ensure_ascii=False,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())