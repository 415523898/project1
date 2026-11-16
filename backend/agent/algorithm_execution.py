"""Run trusted algorithm calls in disposable processes with a shared request budget."""

import contextlib
import contextvars
import math
import os
import pickle
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from config import environment


class AlgorithmTimeout(ValueError):
    code = "algorithm_timeout"


class AlgorithmCancelled(Exception):
    code = "algorithm_cancelled"


_scope = contextvars.ContextVar("algorithm_scope", default=None)


@contextlib.contextmanager
def execution_scope(*, seconds=None, cancelled=None):
    previous = _scope.get() or {}
    deadline = previous.get("deadline")
    if seconds is not None:
        seconds = float(seconds)
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("实验运行上限必须为正数。")
        candidate = time.monotonic() + seconds
        deadline = min(deadline, candidate) if deadline is not None else candidate
    token = _scope.set({"deadline": deadline, "cancelled": cancelled or previous.get("cancelled")})
    try:
        yield
    finally:
        _scope.reset(token)


def check():
    scope = _scope.get() or {}
    if scope.get("cancelled") is not None and scope["cancelled"].is_set():
        raise AlgorithmCancelled("本轮实验已取消，计算已停止。")
    if scope.get("deadline") is not None and time.monotonic() >= scope["deadline"]:
        raise AlgorithmTimeout("实验超过单次运行时间上限，计算已停止。")


class _WindowsJob:
    """Closing this handle terminates only this worker and its descendants."""

    def __init__(self, process):
        import ctypes
        from ctypes import wintypes as wt

        class Basic(ctypes.Structure):
            _fields_ = [
                ("ProcessTime", ctypes.c_int64),
                ("JobTime", ctypes.c_int64),
                ("Flags", wt.DWORD),
                ("MinWorkingSet", ctypes.c_size_t),
                ("MaxWorkingSet", ctypes.c_size_t),
                ("ActiveProcesses", wt.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("Priority", wt.DWORD),
                ("Scheduling", wt.DWORD),
            ]

        class IO(ctypes.Structure):
            _fields_ = [
                (name, ctypes.c_uint64)
                for name in (
                    "ReadOps",
                    "WriteOps",
                    "OtherOps",
                    "ReadBytes",
                    "WriteBytes",
                    "OtherBytes",
                )
            ]

        class Extended(ctypes.Structure):
            _fields_ = [
                ("Basic", Basic),
                ("IO", IO),
                ("ProcessMemory", ctypes.c_size_t),
                ("JobMemory", ctypes.c_size_t),
                ("PeakProcessMemory", ctypes.c_size_t),
                ("PeakJobMemory", ctypes.c_size_t),
            ]

        dll = ctypes.WinDLL("kernel32", use_last_error=True)
        dll.CreateJobObjectW.argtypes = [ctypes.c_void_p, wt.LPCWSTR]
        dll.CreateJobObjectW.restype = wt.HANDLE
        dll.SetInformationJobObject.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD]
        dll.AssignProcessToJobObject.argtypes = [wt.HANDLE, wt.HANDLE]
        dll.TerminateJobObject.argtypes = [wt.HANDLE, wt.UINT]
        dll.QueryInformationJobObject.argtypes = [
            wt.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wt.DWORD,
            ctypes.c_void_p,
        ]
        dll.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
        dll.OpenProcess.restype = wt.HANDLE
        dll.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
        dll.CloseHandle.argtypes = [wt.HANDLE]
        self.dll = dll
        self.handle = dll.CreateJobObjectW(None, None)
        limits = Extended()
        limits.Basic.Flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if (
            not self.handle
            or not dll.SetInformationJobObject(
                self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
            )
            or not dll.AssignProcessToJobObject(self.handle, wt.HANDLE(int(process._handle)))
        ):
            error = ctypes.get_last_error()
            self.close()
            raise OSError(error, "无法建立算法进程回收边界。")

    def close(self):
        if self.handle:
            import ctypes
            from ctypes import wintypes as wt

            class Accounting(ctypes.Structure):
                _fields_ = [
                    (name, ctypes.c_int64)
                    for name in ("User", "Kernel", "PeriodUser", "PeriodKernel")
                ] + [
                    (name, wt.DWORD)
                    for name in ("PageFaults", "TotalProcesses", "ActiveProcesses", "Terminated")
                ]

            # The accounting count may reach zero before Windows finishes process
            # teardown. Wait on process handles too, including venv launchers.
            members = ctypes.create_string_buffer(8 + 4096 * ctypes.sizeof(ctypes.c_size_t))
            handles = []
            if self.dll.QueryInformationJobObject(self.handle, 3, members, len(members), None):
                count = wt.DWORD.from_buffer(members, 4).value
                ids = (ctypes.c_size_t * count).from_buffer(members, 8)
                for pid in ids:
                    handle = self.dll.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
                    if handle:
                        handles.append(handle)
            self.dll.TerminateJobObject(self.handle, 1)
            deadline = time.monotonic() + 5
            for handle in handles:
                self.dll.WaitForSingleObject(
                    handle, max(0, int((deadline - time.monotonic()) * 1000))
                )
                self.dll.CloseHandle(handle)
            while time.monotonic() < deadline:
                value = Accounting()
                if (
                    not self.dll.QueryInformationJobObject(
                        self.handle, 1, ctypes.byref(value), ctypes.sizeof(value), None
                    )
                    or value.ActiveProcesses == 0
                ):
                    break
                time.sleep(0.01)
            self.dll.CloseHandle(self.handle)
            self.handle = None


def _stop(process, job):
    if job:
        job.close()
    elif os.name != "nt":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=5)
    if os.name != "nt":
        # wait() covers only the direct worker; a killed descendant may still be
        # awaiting reaping by its new parent when the worker has already exited.
        deadline = time.monotonic() + 5
        while True:
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                break
            if time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired("algorithm process group", 5)
            time.sleep(0.005)


def run_method(
    method_id,
    table,
    values,
    *,
    root,
    figures_dir=None,
    session_id=None,
    figures=True,
    function=None,
):
    """Only server code chooses the callable; no HTTP payload is deserialized here."""
    from engine import registry

    check()
    workspace = Path(root) / "logs" / "algorithm-workers"
    if environment("FOREST_ENV") == "production":
        from config import DATA_ROOT

        workspace = DATA_ROOT / "algorithm-workers"
    workspace.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="run-", dir=workspace) as temporary:
        folder = Path(temporary)
        staged = folder / "figures"
        request_path, result_path = folder / "request.pickle", folder / "result.pickle"
        with request_path.open("wb") as stream:
            pickle.dump(
                {
                    "function": function or registry.run,
                    "args": (method_id, table, values),
                    "kwargs": {
                        "figures_dir": staged if figures_dir else None,
                        "session_id": session_id,
                        "figures": figures,
                    },
                },
                stream,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        check()
        worker_environment = dict(os.environ)
        worker_environment["PYTHONUTF8"] = "1"
        worker_environment["MPLBACKEND"] = "Agg"
        for name in (
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
        ):
            worker_environment[name] = "1"
        worker = Path(__file__).with_name("algorithm_worker.py")
        process = subprocess.Popen(
            [sys.executable, "-B", str(worker), str(request_path), str(result_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=worker_environment,
            cwd=str(Path(root).resolve()),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            start_new_session=os.name != "nt",
        )
        job = None
        try:
            if os.name == "nt":
                job = _WindowsJob(process)
            # Worker waits here until descendant cleanup is guaranteed.
            process.stdin.write(b"\n")
            process.stdin.close()
            while process.poll() is None:
                check()
                try:
                    process.wait(timeout=0.025)
                except subprocess.TimeoutExpired:
                    pass
            check()
            if process.returncode != 0 or not result_path.is_file():
                raise ValueError("算法工作进程异常退出，本次实验没有保存为成功结果。")
            with result_path.open("rb") as stream:
                response = pickle.load(stream)
            if not response["ok"]:
                raise ValueError(response["error"])
            outcome = response["result"]
            check()
            if figures_dir:
                destination = Path(figures_dir)
                destination.mkdir(parents=True, exist_ok=True)
                for item in outcome.get("figures") or []:
                    name = item.get("name")
                    if name and Path(name).name == name:
                        (staged / name).replace(destination / name)
                        data = staged / (name + ".data.json")
                        if data.is_file() and not data.is_symlink():
                            data.replace(destination / data.name)
            table.notes[:] = response["notes"]
            return outcome
        finally:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            _stop(process, job)
