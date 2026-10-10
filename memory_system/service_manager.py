from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

OK, CONFIG_ERROR, PORT_CONFLICT, IDENTITY_MISMATCH, START_FAILED, HEALTH_FAILED = 0, 2, 3, 4, 5, 6
MEMORY_DIR = Path(__file__).resolve().parent
ROOT = MEMORY_DIR.parent
PYTHON = (ROOT / ".venv" / "Scripts" / "python.exe").resolve()
RUN_SCRIPT = (MEMORY_DIR / "run.py").resolve()
WORKDIR = MEMORY_DIR.resolve()
URL = "http://127.0.0.1:8765"
DB = (MEMORY_DIR / "data" / "memory.db").resolve()
RUN_DIR = MEMORY_DIR / "run"
STATE = RUN_DIR / "memory-service.json"
LOCK = RUN_DIR / "memory-service.lock"
LOG_DIR = MEMORY_DIR / "logs"
OUT_LOG = LOG_DIR / "memory.out.log"
ERR_LOG = LOG_DIR / "memory.err.log"
PORT = 8765


def norm(value: str | Path) -> str:
    return os.path.normcase(os.path.abspath(str(value)))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def output(data: dict[str, Any], json_mode: bool) -> None:
    data.setdefault("service_url", URL)
    print(json.dumps(data, ensure_ascii=False, separators=(",", ":")) if json_mode else f"{data.get('status')}: {data.get('message', '')}", flush=True)


def config_issue() -> str | None:
    missing = [str(p) for p in (PYTHON, RUN_SCRIPT, WORKDIR, DB.parent) if not p.exists()]
    if missing:
        return "missing required path: " + "; ".join(missing)
    if norm(sys.executable) != norm(PYTHON):
        return f"run this manager with {PYTHON}"
    return None


def health(timeout: float = 0.6) -> tuple[bool, dict[str, Any] | None, str | None]:
    try:
        req = urllib.request.Request(URL + "/api/health", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        good = isinstance(data, dict) and data.get("status") == "ok"
        return good, data if isinstance(data, dict) else None, None if good else "unexpected health response"
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return False, None, f"{type(exc).__name__}: {exc}"


def listeners() -> list[int]:
    found: set[int] = set()
    try:
        for item in psutil.net_connections(kind="inet"):
            if item.status == psutil.CONN_LISTEN and item.laddr and int(item.laddr.port) == PORT and item.pid:
                found.add(int(item.pid))
    except psutil.Error:
        pass
    return sorted(found)


def snapshot(pid: int) -> dict[str, Any] | None:
    try:
        proc = psutil.Process(int(pid))
        return {"pid": proc.pid, "create_time": proc.create_time(), "exe": proc.exe(), "cmdline": proc.cmdline(), "cwd": proc.cwd()}
    except (psutil.Error, ValueError):
        return None


def matches_process(info: dict[str, Any] | None) -> tuple[bool, str]:
    if not info:
        return False, "process_not_found"
    cmd = [norm(x.strip('"')) for x in info.get("cmdline", []) if x]
    if norm(RUN_SCRIPT) not in cmd:
        return False, "run_script_mismatch"
    if norm(PYTHON) not in cmd and norm(info.get("exe", "")) != norm(PYTHON):
        return False, "python_path_mismatch"
    if info.get("cwd") and norm(info["cwd"]) != norm(WORKDIR):
        return False, "working_directory_mismatch"
    return True, "matched"


def descendants(pid: int) -> set[int]:
    try:
        return {child.pid for child in psutil.Process(pid).children(recursive=True)}
    except psutil.Error:
        return set()


def load_state() -> dict[str, Any] | None:
    try:
        data = json.loads(STATE.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else None
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


def save_state(data: dict[str, Any]) -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    temporary = STATE.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, STATE)


def remove_state() -> None:
    try:
        STATE.unlink()
    except FileNotFoundError:
        pass


def make_state(pid: int, started_at: str | None = None, launcher_pid: int | None = None) -> dict[str, Any]:
    info = snapshot(pid)
    if not info:
        raise RuntimeError("service process disappeared")
    data = {"pid": pid, "process_create_time": info["create_time"], "python_path": str(PYTHON), "script_path": str(RUN_SCRIPT), "working_directory": str(WORKDIR), "service_url": URL, "database_path": str(DB), "started_at": started_at or now()}
    if launcher_pid and launcher_pid != pid:
        launcher = snapshot(launcher_pid)
        if launcher:
            data.update({"launcher_pid": launcher_pid, "launcher_create_time": launcher["create_time"]})
    return data


def validate_state(data: dict[str, Any] | None) -> tuple[bool, str, dict[str, Any] | None]:
    required = ("pid", "process_create_time", "python_path", "script_path", "working_directory", "service_url", "database_path", "started_at")
    if not data:
        return False, "state_missing", None
    if any(key not in data for key in required):
        return False, "state_fields_missing", None
    for key, value in (("python_path", PYTHON), ("script_path", RUN_SCRIPT), ("working_directory", WORKDIR), ("database_path", DB)):
        if norm(data[key]) != norm(value):
            return False, f"state_{key}_mismatch", None
    info = snapshot(int(data["pid"]))
    matched, reason = matches_process(info)
    if not matched:
        return False, reason, info
    if abs(float(info["create_time"]) - float(data["process_create_time"])) > 0.01:
        return False, "process_create_time_mismatch", info
    return True, "matched", info


@contextmanager
def exclusive_lock(timeout: float = 10.0):
    import msvcrt
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    handle = LOCK.open("a+b")
    if LOCK.stat().st_size == 0:
        handle.write(b"0")
        handle.flush()
    deadline = time.monotonic() + timeout
    locked = False
    try:
        while time.monotonic() < deadline:
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                locked = True
                break
            except OSError:
                time.sleep(0.1)
        if not locked:
            raise TimeoutError("memory service lock timeout")
        yield
    finally:
        if locked:
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        handle.close()


def terminate_one(pid: int, create_time: float, wait_seconds: float) -> bool:
    try:
        proc = psutil.Process(pid)
        if abs(proc.create_time() - create_time) > 0.01:
            return False
        proc.terminate()
        try:
            proc.wait(timeout=wait_seconds)
        except psutil.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        return True
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return True
    except psutil.Error:
        return False


def terminate_owned(data: dict[str, Any], wait_seconds: float = 10.0) -> tuple[bool, list[int]]:
    pid = int(data["pid"])
    try:
        proc = psutil.Process(pid)
        if abs(proc.create_time() - float(data["process_create_time"])) > 0.01:
            return False, []
        children = proc.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        children = []
    except psutil.Error:
        return False, []
    ended = terminate_one(pid, float(data["process_create_time"]), wait_seconds)
    for child in children:
        try:
            terminate_one(child.pid, child.create_time(), 3)
        except psutil.Error:
            pass
    launcher_pid = data.get("launcher_pid")
    launcher_time = data.get("launcher_create_time")
    if launcher_pid and launcher_time:
        terminate_one(int(launcher_pid), float(launcher_time), 3)
    return ended, [child.pid for child in children]


def start_locked() -> tuple[int, dict[str, Any]]:
    issue = config_issue()
    if issue:
        return CONFIG_ERROR, {"status": "config_error", "message": issue}
    good, health_data, _ = health()
    pids = listeners()
    if good:
        valid, _, info = validate_state(load_state())
        if valid and info and info["pid"] in pids:
            return OK, {"status": "already_running", "message": "memory service is already healthy", "pid": info["pid"], "process_create_time": info["create_time"], "health": health_data}
        if len(pids) == 1:
            info = snapshot(pids[0])
            matched, _ = matches_process(info)
            if matched:
                data = make_state(pids[0])
                save_state(data)
                return OK, {"status": "already_running", "message": "healthy formal service adopted", "pid": data["pid"], "process_create_time": data["process_create_time"], "health": health_data}
        return PORT_CONFLICT, {"status": "port_conflict", "message": "healthy responder is not the formal service", "listener_pids": pids}
    old = load_state()
    if old:
        valid, _, _ = validate_state(old)
        if valid:
            return HEALTH_FAILED, {"status": "health_failed", "message": "formal process exists but is unhealthy", "pid": old["pid"]}
        remove_state()
    pids = listeners()
    if pids:
        return PORT_CONFLICT, {"status": "port_conflict", "message": "port 8765 is occupied by an unknown process", "listener_pids": pids}
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "MEMORY_HOST": "127.0.0.1", "MEMORY_PORT": str(PORT), "MEMORY_DB_PATH": str(DB)})
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    with OUT_LOG.open("ab", buffering=0) as out, ERR_LOG.open("ab", buffering=0) as err:
        launcher = subprocess.Popen([str(PYTHON), str(RUN_SCRIPT)], cwd=str(WORKDIR), stdin=subprocess.DEVNULL, stdout=out, stderr=err, env=env, shell=False, creationflags=flags, close_fds=True)
    started_at = now()
    deadline = time.monotonic() + 15
    detail = "health endpoint did not become ready"
    while time.monotonic() < deadline:
        if launcher.poll() is not None:
            detail = f"launcher exited with code {launcher.returncode}"
            break
        good, health_data, error = health()
        if good:
            pids = listeners()
            owned = descendants(launcher.pid) | {launcher.pid}
            candidates = [pid for pid in pids if pid in owned and matches_process(snapshot(pid))[0]]
            if len(candidates) == 1:
                data = make_state(candidates[0], started_at, launcher.pid)
                save_state(data)
                return OK, {"status": "ready", "message": "memory service is healthy", "pid": data["pid"], "process_create_time": data["process_create_time"], "launcher_pid": launcher.pid, "health": health_data}
            detail = f"healthy listener identity mismatch: {pids}"
        else:
            detail = error or detail
        time.sleep(0.15)
    info = snapshot(launcher.pid)
    if info:
        failed_state = make_state(launcher.pid, started_at)
        failed_state["pid"] = launcher.pid
        failed_state["process_create_time"] = info["create_time"]
        failed_state["launcher_pid"] = launcher.pid
        failed_state["launcher_create_time"] = info["create_time"]
        terminate_owned(failed_state, 2)
    remove_state()
    return START_FAILED, {"status": "start_failed", "message": detail, "pid": launcher.pid}


def stop_locked() -> tuple[int, dict[str, Any]]:
    data = load_state()
    good, _, _ = health()
    pids = listeners()
    if not data:
        if not good and not pids:
            return OK, {"status": "already_stopped", "message": "memory service is already stopped"}
        return IDENTITY_MISMATCH, {"status": "identity_mismatch", "message": "state is missing; no process was ended", "listener_pids": pids}
    valid, reason, info = validate_state(data)
    if not valid or not info:
        return IDENTITY_MISMATCH, {"status": "identity_mismatch", "message": reason, "pid": data.get("pid"), "listener_pids": pids}
    if pids and int(data["pid"]) not in pids:
        return IDENTITY_MISMATCH, {"status": "identity_mismatch", "message": "listener pid differs from state", "pid": data["pid"], "listener_pids": pids}
    ended, children = terminate_owned(data, 10)
    if not ended and psutil.pid_exists(int(data["pid"])):
        return IDENTITY_MISMATCH, {"status": "identity_mismatch", "message": "recorded process could not be ended safely", "pid": data["pid"]}
    deadline = time.monotonic() + 5
    while listeners() and time.monotonic() < deadline:
        time.sleep(0.1)
    remaining = listeners()
    if remaining:
        return HEALTH_FAILED, {"status": "health_failed", "message": "port remained occupied", "listener_pids": remaining}
    remove_state()
    return OK, {"status": "stopped", "message": "memory service stopped", "pid": data["pid"], "child_pids": children}


def start_command() -> tuple[int, dict[str, Any]]:
    try:
        with exclusive_lock():
            return start_locked()
    except TimeoutError as exc:
        return START_FAILED, {"status": "start_failed", "message": str(exc)}


def stop_command() -> tuple[int, dict[str, Any]]:
    try:
        with exclusive_lock():
            return stop_locked()
    except TimeoutError as exc:
        return START_FAILED, {"status": "start_failed", "message": str(exc)}


def restart_command() -> tuple[int, dict[str, Any]]:
    try:
        with exclusive_lock():
            old = load_state()
            old_pid = old.get("pid") if old else None
            code, stopped = stop_locked()
            if code != OK:
                return code, {"status": "restart_failed", "message": "stop phase failed", "stop": stopped}
            code, started = start_locked()
            if code != OK:
                return code, {"status": "restart_failed", "message": "start phase failed", "stop": stopped, "start": started}
            return OK, {"status": "ready", "message": "memory service restarted", "old_pid": old_pid, "pid": started.get("pid"), "stop": stopped, "start": started}
    except TimeoutError as exc:
        return START_FAILED, {"status": "restart_failed", "message": str(exc)}


def status_command() -> tuple[int, dict[str, Any]]:
    issue = config_issue()
    if issue:
        return CONFIG_ERROR, {"status": "config_error", "message": issue}
    data = load_state()
    good, health_data, detail = health()
    pids = listeners()
    if not data:
        if good or pids:
            return IDENTITY_MISMATCH, {"status": "identity_mismatch", "message": "listener exists without valid state", "healthy": good, "listener_pids": pids}
        return OK, {"status": "stopped", "message": "memory service is stopped", "healthy": False, "listener_pids": []}
    valid, reason, _ = validate_state(data)
    if not valid:
        return IDENTITY_MISMATCH, {"status": "identity_mismatch", "message": reason, "healthy": good, "pid": data.get("pid"), "listener_pids": pids}
    if not good:
        return HEALTH_FAILED, {"status": "health_failed", "message": detail or "health check failed", "healthy": False, "pid": data["pid"], "listener_pids": pids}
    if int(data["pid"]) not in pids:
        return IDENTITY_MISMATCH, {"status": "identity_mismatch", "message": "healthy listener differs from state", "pid": data["pid"], "listener_pids": pids}
    return OK, {"status": "ready", "message": "memory service is healthy", "healthy": True, "pid": data["pid"], "process_create_time": data["process_create_time"], "started_at": data["started_at"], "health": health_data, "listener_pids": pids}


def health_command() -> tuple[int, dict[str, Any]]:
    good, health_data, detail = health()
    if good:
        return OK, {"status": "healthy", "message": "health endpoint returned ok", "healthy": True, "health": health_data, "listener_pids": listeners()}
    return HEALTH_FAILED, {"status": "unhealthy", "message": detail or "health endpoint failed", "healthy": False, "listener_pids": listeners()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("start", "stop", "restart", "status", "health"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    commands = {"start": start_command, "stop": stop_command, "restart": restart_command, "status": status_command, "health": health_command}
    code, data = commands[args.command]()
    data["exit_code"] = code
    output(data, args.json)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
