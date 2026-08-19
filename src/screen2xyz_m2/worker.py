"""Worker-process client: protocol m2w.1, lifecycle, bounded reader.

The client is mechanical: one outstanding request, generation/revision/mode
matching, stale-reply rejection, exact teardown order, and job-object
hardening. Failure *counters* and backoff policy live in the controller.
"""

from __future__ import annotations

import gc
import json
import os
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable

from . import contracts as C
from .paths import repository_root


class WorkerError(RuntimeError):
    """Protocol or lifecycle failure; worker_status carries the class."""

    def __init__(self, worker_status: str, detail: str = "") -> None:
        super().__init__(f"{worker_status}: {detail}")
        self.worker_status = worker_status
        self.detail = detail


class WorkerTimeout(WorkerError):
    def __init__(self, detail: str = "") -> None:
        super().__init__("REQUEST_TIMEOUT", detail)


def _assign_job_object(handle: int) -> None:
    """Best-effort kill-on-close job object (orphan hardening)."""

    if sys.platform != "win32":
        return
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in
                    ("ReadOperationCount", "WriteOperationCount",
                     "OtherOperationCount", "ReadTransferCount",
                     "WriteTransferCount", "OtherTransferCount")]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [("BasicLimitInformation",
                     JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
    kernel32.SetInformationJobObject(job, 9, ctypes.byref(info),
                                     ctypes.sizeof(info))
    kernel32.AssignProcessToJobObject(job, handle)
    # The job handle is intentionally leaked into this process: when the UI
    # process dies, the kernel closes it and the worker is killed.


class WorkerClient:
    """One worker generation. A new generation means a new WorkerClient."""

    def __init__(self, *,
                 session_id: str,
                 scope: dict[str, Any],
                 backend: str,
                 ocr_language: str = "en-US",
                 cursor_metadata: bool = False,
                 worker_script: Path | None = None,
                 spawn_command: list[str] | None = None) -> None:
        self.session_id = session_id
        self.scope = scope
        self.backend = backend
        self.ocr_language = ocr_language
        self.cursor_metadata = cursor_metadata
        self.generation = f"gen-{secrets.token_hex(4)}"
        self.capabilities: dict[str, Any] = {}
        self._script = worker_script or (
            repository_root() / "src/screen2xyz_m2/adapters/"
            "capture_worker_windows.ps1")
        self._spawn_command = spawn_command
        self._proc: subprocess.Popen | None = None
        self._stdout_queue: "Queue[dict[str, Any] | None]" = Queue()
        self.stderr_lines: list[str] = []
        self._lock = threading.Lock()
        self._alive = False
        self._readers: list[threading.Thread] = []

    # -- lifecycle --------------------------------------------------------

    def start(self, *, restore_session_state: str,
              configuration_revision: int,
              init_timeout_ms: int = 15000) -> dict[str, Any]:
        # Tk values must be finalized by the thread that owns their Tcl
        # interpreter.  Starting the pipe-reader threads can otherwise be
        # the first allocation boundary that runs cyclic GC, which makes a
        # stale Tk cycle fatal (``Tcl_AsyncDelete``) on a reader thread.  A
        # worker is started from the UI/main thread in the product; keep the
        # defensive collection explicitly main-thread-only for embedders.
        if threading.current_thread() is threading.main_thread():
            gc.collect()
        command = self._spawn_command or [
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", str(self._script)]
        creationflags = (subprocess.CREATE_NO_WINDOW
                         if sys.platform == "win32" else 0)
        # Binary pipes so the stdout reader can bound each line by BYTES via
        # read1() before a full unbounded line is ever allocated.
        try:
            self._proc = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, creationflags=creationflags)
        except OSError as exc:
            # A blocked/missing powershell.exe, an AV-quarantined or moved
            # capture_worker_windows.ps1, or a restrictive execution policy
            # raises a plain OSError/FileNotFoundError/PermissionError here
            # - never a WorkerError. Every caller in ui/app.py only catches
            # WorkerError, so an uncaught OSError would silently freeze
            # whatever Step 2/3/4 screen is waiting on this worker (the same
            # failure shape as the reported "Test capture does nothing" bug,
            # just from a different cause). Convert it so it is always
            # visibly reported instead.
            raise WorkerError("PROCESS_EXITED",
                              f"could not start capture worker: {exc}"
                              ) from exc
        if sys.platform == "win32" and self._proc._handle:  # type: ignore
            _assign_job_object(int(self._proc._handle))  # type: ignore
        self._alive = True
        out_reader = threading.Thread(target=self._read_stdout, daemon=True)
        err_reader = threading.Thread(target=self._read_stderr, daemon=True)
        out_reader.start()
        err_reader.start()
        self._readers = [out_reader, err_reader]
        self._expected_revision = configuration_revision
        # Any INIT failure tears this worker down before raising, so a
        # half-initialized child/threads/pipes are never left running.
        try:
            reply = self.request(
                "INIT",
                {"protocol_version": C.PROTOCOL_VERSION,
                 "session_id": self.session_id,
                 "worker_generation": self.generation,
                 "configuration_revision": configuration_revision,
                 "restore_session_state": restore_session_state,
                 "scope": self.scope,
                 "backend": self.backend,
                 "ocr_language": self.ocr_language,
                 "cursor_metadata": self.cursor_metadata,
                 "parent_pid": os.getpid()},
                timeout_ms=init_timeout_ms,
                ui_session_state=None,
                expected_mode=None)
            if reply.get("worker_status") != "OK":
                raise WorkerError("PROTOCOL_ERROR",
                                  str(reply.get("error", "INIT failed")))
            if reply.get("dpi_awareness") != "per_monitor_v2":
                raise WorkerError("PROTOCOL_ERROR",
                                  f"worker DPI awareness "
                                  f"{reply.get('dpi_awareness')!r} != PMv2")
            if reply.get("restore_session_state") != restore_session_state:
                raise WorkerError("PROTOCOL_ERROR",
                                  "restored-state echo mismatch")
        except WorkerError:
            self.teardown()
            raise
        self.capabilities = reply
        return reply

    def _read_stdout(self) -> None:
        proc = self._proc
        assert proc is not None and proc.stdout is not None
        stream = proc.stdout  # BufferedReader (binary)
        buffer = bytearray()
        read1 = getattr(stream, "read1", None)
        try:
            while True:
                chunk = read1(65536) if read1 else stream.read(65536)
                if not chunk:
                    break
                buffer.extend(chunk)
                while True:
                    newline = buffer.find(b"\n")
                    if newline < 0:
                        # Fail closed once an UNTERMINATED line exceeds the
                        # cap, before it can grow unbounded.
                        if len(buffer) > C.JSON_LINE_MAX_BYTES:
                            self.stderr_lines.append(
                                "stdout line over 96 MiB bound")
                            self._stdout_queue.put(None)
                            return
                        break
                    raw = bytes(buffer[:newline])
                    del buffer[:newline + 1]
                    if len(raw) > C.JSON_LINE_MAX_BYTES:
                        self.stderr_lines.append(
                            "stdout line over 96 MiB bound")
                        self._stdout_queue.put(None)
                        return
                    text = raw.decode("utf-8", errors="replace").strip()
                    if not text:
                        continue
                    try:
                        self._stdout_queue.put(json.loads(text))
                    except json.JSONDecodeError:
                        self.stderr_lines.append("malformed stdout line")
                        self._stdout_queue.put(None)
                        return
        except (ValueError, OSError):
            pass
        finally:
            self._stdout_queue.put(None)

    def _read_stderr(self) -> None:
        proc = self._proc
        assert proc is not None and proc.stderr is not None
        try:
            for raw in proc.stderr:                     # binary lines
                line = raw.decode("utf-8", errors="replace").rstrip()
                if line:
                    self.stderr_lines.append(line[:2000])
        except (ValueError, OSError):
            pass

    @property
    def alive(self) -> bool:
        return (self._alive and self._proc is not None
                and self._proc.poll() is None)

    # -- protocol ---------------------------------------------------------

    def request(self, command: str, payload: dict[str, Any], *,
                timeout_ms: int,
                ui_session_state: str | None,
                configuration_revision: int | None = None,
                expected_mode: str | None = "__unset__") -> dict[str, Any]:
        """Send one request; enforce the single-outstanding invariant."""

        if not self._lock.acquire(blocking=False):
            raise WorkerError("PROTOCOL_ERROR",
                              "overlapping worker request refused")
        try:
            if not self.alive:
                raise WorkerError("PROCESS_EXITED", "worker not running")
            request_id = f"req-{secrets.token_hex(6)}"
            message: dict[str, Any] = {"command": command,
                                       "request_id": request_id,
                                       "worker_generation": self.generation,
                                       **payload}
            if ui_session_state is not None:
                message["ui_session_state"] = ui_session_state
            if configuration_revision is not None:
                message["configuration_revision"] = configuration_revision
            assert self._proc is not None and self._proc.stdin is not None
            try:
                self._proc.stdin.write(
                    (json.dumps(message) + "\n").encode("utf-8"))
                self._proc.stdin.flush()
            except OSError as exc:
                raise WorkerError("PROCESS_EXITED", str(exc)) from exc
            deadline = time.monotonic() + timeout_ms / 1000.0
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise WorkerTimeout(f"{command} exceeded {timeout_ms} ms")
                try:
                    reply = self._stdout_queue.get(timeout=remaining)
                except Empty:
                    raise WorkerTimeout(f"{command} exceeded {timeout_ms} ms")
                if reply is None:
                    raise WorkerError("PROCESS_EXITED",
                                      "worker stream ended or malformed")
                mismatch = (
                    reply.get("request_id") != request_id
                    or reply.get("worker_generation") != self.generation)
                if configuration_revision is not None \
                        and reply.get("configuration_revision") \
                        != configuration_revision:
                    mismatch = True
                if expected_mode not in ("__unset__", None) \
                        and reply.get("worker_mode") != expected_mode:
                    mismatch = True
                if mismatch:
                    self.stderr_lines.append(
                        f"stale/mismatched reply dropped: "
                        f"{reply.get('request_id')}")
                    continue
                return reply
        finally:
            self._lock.release()

    # -- teardown (exact order from architecture §6) ----------------------

    def teardown(self, *, graceful_ms: int = 0,
                 deadline_s: float | None = None) -> None:
        """Invalidate generation; kill/reap; drain; close; join readers.

        `deadline_s` caps the TOTAL wall-clock spent here (used by the ≤2 s
        emergency path); daemon reader threads are abandoned if the budget
        runs out rather than blocking past the bound.
        """

        self._alive = False
        proc = self._proc
        if proc is None:
            return
        end = None if deadline_s is None else time.monotonic() + deadline_s

        def remaining(default: float) -> float:
            if end is None:
                return default
            return max(0.0, end - time.monotonic())

        if graceful_ms and proc.poll() is None:
            try:
                proc.wait(timeout=min(graceful_ms / 1000.0, remaining(
                    graceful_ms / 1000.0)))
            except subprocess.TimeoutExpired:
                pass
        if proc.poll() is None:
            proc.kill()
        try:
            proc.wait(timeout=remaining(5))
        except subprocess.TimeoutExpired:
            pass
        try:
            while True:
                self._stdout_queue.get_nowait()
        except Empty:
            pass
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            try:
                if stream:
                    stream.close()
            except OSError:
                pass
        for reader in self._readers:
            reader.join(timeout=remaining(2))
        self._proc = None

    def graceful_shutdown(self, ui_session_state: str,
                          configuration_revision: int) -> None:
        """STOP (if recording/paused) then SHUTDOWN, then kill within bound."""

        try:
            self.request("SHUTDOWN", {}, timeout_ms=C.GRACEFUL_SHUTDOWN_MS,
                         ui_session_state=ui_session_state,
                         configuration_revision=configuration_revision)
        except WorkerError:
            pass
        self.teardown(graceful_ms=C.GRACEFUL_SHUTDOWN_MS)
