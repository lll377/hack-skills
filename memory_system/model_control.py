from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


# ======================== 模型配置区 ========================
# 只需要在这里配置一次。API Key 不会写入 memory.db 或状态文件。
MODEL_API_KEY = "sk-EHjIqJw1WnWPZP9OTR4eWXysrXL7A4mrpmVhWYAenAsG9aNb"
MODEL_BASE_URL = "https://api.ntrapi.cn/v1"
MODEL_NAME = "gpt-5.4"
# ===========================================================


MEMORY_DIR = Path(__file__).resolve().parent
ROOT = MEMORY_DIR.parent
VENV_PYTHON = (ROOT / ".venv" / "Scripts" / "python.exe").resolve()
SERVICE_MANAGER = (MEMORY_DIR / "service_manager.py").resolve()
RUN_SCRIPT = (MEMORY_DIR / "run.py").resolve()
MODE_FILE = MEMORY_DIR / "run" / "model-mode.json"
HEALTH_URL = "http://127.0.0.1:8765/api/health"


def ensure_formal_python() -> None:
    """Ensure service_manager receives the exact project virtualenv Python."""
    if os.path.normcase(os.path.abspath(sys.executable)) == os.path.normcase(
        os.path.abspath(VENV_PYTHON)
    ):
        return
    if not VENV_PYTHON.is_file():
        raise SystemExit(f"找不到项目Python：{VENV_PYTHON}")
    completed = subprocess.run([str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])
    raise SystemExit(completed.returncode)


def validate_config() -> None:
    if not MODEL_API_KEY.strip() or MODEL_API_KEY == "请在这里填写API_KEY":
        raise SystemExit("开启失败：请先在 model_control.py 顶部填写 MODEL_API_KEY。")
    if not MODEL_BASE_URL.startswith(("http://", "https://")):
        raise SystemExit("开启失败：MODEL_BASE_URL 必须是有效的HTTP(S)地址。")
    if not MODEL_NAME.strip():
        raise SystemExit("开启失败：MODEL_NAME 不能为空。")


def service_environment(enabled: bool) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "MEMORY_OPENAI_API_KEY": MODEL_API_KEY if enabled else "",
            "MEMORY_OPENAI_BASE_URL": MODEL_BASE_URL,
            "MEMORY_OPENAI_MODEL": MODEL_NAME,
        }
    )
    return env


def run_manager(command: str, enabled: bool) -> tuple[int, dict]:
    completed = subprocess.run(
        [str(VENV_PYTHON), str(SERVICE_MANAGER), command, "--json"],
        cwd=str(ROOT),
        env=service_environment(enabled),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = completed.stdout.strip()
    try:
        payload = json.loads(output) if output else {}
    except json.JSONDecodeError:
        payload = {"status": "invalid_output", "message": output or completed.stderr.strip()}
    return completed.returncode, payload


def stop_direct_service_if_needed() -> bool:
    """Adopt the first switch from a service started with start.ps1/python run.py.

    Only the expected memory_system/run.py process listening on port 8765 may be
    stopped. Unrelated listeners are never terminated.
    """
    try:
        import psutil
    except ImportError:
        return False

    expected = os.path.normcase(os.path.abspath(RUN_SCRIPT))
    stopped = False
    for item in psutil.net_connections(kind="inet"):
        if not item.laddr or int(item.laddr.port) != 8765 or not item.pid:
            continue
        try:
            process = psutil.Process(int(item.pid))
            command_line = [
                os.path.normcase(os.path.abspath(value.strip('"')))
                for value in process.cmdline()
                if value
            ]
            if expected not in command_line:
                raise SystemExit(
                    f"端口8765被其他程序占用，已拒绝结束进程：PID {process.pid}"
                )
            process.terminate()
            try:
                process.wait(timeout=10)
            except psutil.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            stopped = True
        except psutil.NoSuchProcess:
            pass
    return stopped


def save_mode(enabled: bool) -> None:
    MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
    MODE_FILE.write_text(
        json.dumps(
            {
                "enabled": enabled,
                "model": MODEL_NAME,
                "base_url": MODEL_BASE_URL,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_mode() -> bool:
    try:
        data = json.loads(MODE_FILE.read_text(encoding="utf-8"))
        return bool(data.get("enabled", False))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return False


def health(retries: int = 20) -> dict:
    error = "服务尚未就绪"
    for _ in range(retries):
        try:
            request = urllib.request.Request(
                HEALTH_URL,
                headers={"Accept": "application/json", "Cache-Control": "no-cache"},
            )
            with urllib.request.urlopen(request, timeout=2) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            error = str(exc)
            time.sleep(0.25)
    raise SystemExit(f"记忆服务健康检查失败：{error}")


def switch(enabled: bool) -> None:
    if enabled:
        validate_config()

    code, result = run_manager("restart", enabled)
    if code != 0:
        # The existing foreground start.ps1 service has no manager-owned state.
        stop_direct_service_if_needed()
        code, result = run_manager("start", enabled)
    if code != 0:
        raise SystemExit(
            "切换失败：" + json.dumps(result, ensure_ascii=False, indent=2)
        )

    save_mode(enabled)
    data = health()
    actual = bool(data.get("model", {}).get("enabled", False))
    if actual != enabled:
        raise SystemExit(
            "切换后的状态与预期不一致：" + json.dumps(data, ensure_ascii=False)
        )

    mode_name = "模型增强模式" if enabled else "本地快速模式"
    print(f"切换成功：{mode_name}")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def show_status() -> None:
    data = health(retries=1)
    print(json.dumps(data, ensure_ascii=False, indent=2))


def restart_current_mode() -> None:
    switch(load_mode())


def main() -> int:
    ensure_formal_python()
    if len(sys.argv) != 2 or sys.argv[1].lower() not in {
        "on",
        "off",
        "restart",
        "status",
    }:
        print("用法：python model_control.py on|off|restart|status")
        return 2

    command = sys.argv[1].lower()
    if command == "on":
        switch(True)
    elif command == "off":
        switch(False)
    elif command == "restart":
        restart_current_mode()
    else:
        show_status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
