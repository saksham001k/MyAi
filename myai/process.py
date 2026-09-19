"""Owned, cancellable processes. A working directory is not an OS sandbox."""
import os
import signal
import subprocess
import tempfile
import time
import shlex


def split_command(command):
    """Parse platform quoting without invoking a shell or losing Windows slashes."""
    if os.name != 'nt':
        return shlex.split(command)
    import ctypes
    from ctypes import wintypes
    shell32 = ctypes.WinDLL('shell32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    shell32.CommandLineToArgvW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    shell32.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    count = ctypes.c_int()
    args = shell32.CommandLineToArgvW(command.strip(), ctypes.byref(count))
    if not args:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return [args[index] for index in range(count.value)]
    finally:
        kernel32.LocalFree(args)


def run_process(argv, cwd, cancel, timeout=120):
    if not isinstance(argv, list) or not argv or any(not isinstance(a, str) or not a for a in argv):
        raise ValueError('Use a non-empty argument list, not a shell expression.')
    if type(timeout) not in (int, float) or not 0 < timeout <= 300:
        raise ValueError('Timeout must be between 1 and 300 seconds.')
    if cancel.is_set():
        return {'returncode': None, 'cancelled': True, 'output': ''}
    env = {k: v for k, v in os.environ.items() if k in ('PATH', 'SYSTEMROOT', 'WINDIR', 'TMPDIR', 'TEMP', 'TMP', 'LANG')}
    started = time.monotonic()
    with tempfile.TemporaryFile() as out:
        child = subprocess.Popen(argv, cwd=cwd, env=env, stdout=out, stderr=subprocess.STDOUT,
                                 start_new_session=os.name != 'nt')
        reason = None
        try:
            while child.poll() is None:
                if cancel.wait(.1):
                    reason = 'cancelled'
                    break
                if time.monotonic() - started > timeout:
                    reason = 'timed_out'
                    break
                if out.tell() > 8 * 1024 * 1024:
                    reason = 'output_limit'
                    break
        finally:
            if child.poll() is None:
                if os.name != 'nt':
                    try:
                        os.killpg(child.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                else:
                    child.terminate()
                try:
                    child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    if os.name != 'nt':
                        try:
                            os.killpg(child.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    else:
                        child.kill()
                    child.wait(timeout=3)
            out.seek(0, 2)
            size = out.tell()
            out.seek(max(0, size - 16000))
            output = out.read().decode('utf-8', 'replace')
    return {'returncode': child.returncode, 'output': output,
            'output_truncated': size > 16000, 'cancelled': reason == 'cancelled',
            'timed_out': reason == 'timed_out', 'limit': reason,
            'seconds': round(time.monotonic() - started, 2)}
