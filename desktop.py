"""Windowed Windows entrypoint. Launch using MyAi.vbs or the desktop shortcut."""
import ctypes
from ctypes import wintypes
import hashlib
import html
import logging
import os
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent


def acquire_instance(root):
    """Hold a kernel mutex; Windows releases it even after a crash."""
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    name = 'Local\\MyAi-' + hashlib.sha256(str(root).lower().encode()).hexdigest()[:24]
    handle = kernel.CreateMutexW(None, False, name)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    return handle, ctypes.get_last_error() != 183


def activate_existing():
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user.FindWindowW.restype = wintypes.HWND
    user.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user.SetForegroundWindow.argtypes = [wintypes.HWND]
    for _ in range(150):
        window = user.FindWindowW(None, 'KISS') or user.FindWindowW(None, 'MyAi')
        if window:
            user.ShowWindow(window, 9)
            user.SetForegroundWindow(window)
            return
        time.sleep(0.1)


def ensure_window_runtime():
    try:
        import webview
        return webview
    except ImportError:
        import subprocess
        import tkinter as tk
        from tkinter import ttk
        dialog = tk.Tk()
        dialog.title('KISS setup')
        dialog.geometry('440x150')
        ttk.Label(dialog, text='Preparing KISS for its first launch…').pack(pady=20)
        ttk.Label(dialog, text='Downloading the desktop window component. Internet is required.').pack()
        progress = ttk.Progressbar(dialog, mode='indeterminate')
        progress.pack(fill='x', padx=25, pady=15)
        progress.start()
        result = []
        def install():
            try:
                python = Path(sys.executable).with_name('python.exe')
                subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(ROOT / 'requirements-desktop.txt')],
                               check=True, stdout=sys.stderr, stderr=sys.stderr,
                               creationflags=subprocess.CREATE_NO_WINDOW)
                result.append(None)
            except Exception as exc:
                result.append(exc)
        threading.Thread(target=install, daemon=True).start()
        def poll():
            if result:
                dialog.destroy()
            else:
                dialog.after(100, poll)
        dialog.after(100, poll)
        dialog.mainloop()
        if not result or result[0]:
            raise RuntimeError('Desktop setup did not complete. Check your internet connection and open KISS again.')
        import webview
        return webview


def run_window(webview, auto_close=0):
    from myai.engine import Engine
    from myai.desktop_memory import DesktopMemory
    from myai.hardware import detect_hardware
    from myai.server import App, make_server
    from run import close_app
    # Show the window immediately; initialize the existing backend in a worker.
    window = webview.create_window('KISS', html='''<html><body style="background:#101827;color:#edf2fa;
        font:18px Segoe UI;padding:64px"><h1>KISS</h1><p>Starting your local assistant…</p></body></html>''',
        width=1280, height=850, min_size=(900, 600))
    ready = threading.Event()
    started = threading.Event()
    closing = threading.Event()
    state = {}
    memory = DesktopMemory(ROOT)
    def start_backend():
        started.set()
        try:
            adapter = memory.start()
            app = App(ROOT, ROOT / 'web', Engine(ROOT, hardware=detect_hardware()), shared_memory=adapter)
            logging.info('Shared-memory connection: %s', adapter.status())
            state['app'] = app
            server = make_server(app)
            state['server'] = server
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            state['thread'] = thread
            logging.info('Local service ready on port %s', server.server_port)
            if not closing.is_set():
                window.load_url(f'http://127.0.0.1:{server.server_port}/#token={app.token}')
        except Exception as exc:
            logging.exception('MyAi startup failed')
            if not closing.is_set():
                window.load_html('<h1>KISS could not start</h1><p>' + html.escape(str(exc)) +
                                 '</p><p>Details are in data/desktop.log in your application folder.</p>')
        finally:
            ready.set()
        if auto_close:
            time.sleep(auto_close)
            window.destroy()
    def on_closed():
        closing.set()
    def on_loaded():
        if state.get('server'):
            logging.info('Desktop interface loaded')
            if auto_close:
                content = window.evaluate_js('document.body.innerText')
                logging.info('Desktop smoke check: interface has content=%s', bool(content and len(content) > 100))
                window.evaluate_js("fetch('/api/status', {headers: {Authorization: 'Bearer ' + sessionStorage.getItem('myai-token')}}).then(r => r.status)",
                                   callback=lambda status: logging.info('Desktop smoke check: authenticated API status=%s', status))
    window.events.closed += on_closed
    window.events.loaded += on_loaded
    try:
        webview.start(start_backend, gui='edgechromium', icon=str(ROOT / 'web' / 'kiss.ico'), storage_path=str(ROOT / 'data' / 'desktop-webview'))
    finally:
        closing.set()
        if started.is_set():
            ready.wait()
        server = state.get('server')
        if server:
            server.shutdown()
        app = state.get('app')
        if app:
            close_app(app)
        if server:
            server.server_close()
            state['thread'].join(timeout=5)
        memory.close()
        logging.info('Desktop shutdown complete')


def main():
    if os.name != 'nt':
        raise RuntimeError('This desktop launcher currently supports Windows.')
    (ROOT / 'data').mkdir(exist_ok=True)
    # pythonw has no standard streams; retain local diagnostics without a console.
    log = open(ROOT / 'data' / 'desktop.log', 'a', encoding='utf-8', buffering=1)
    sys.stdout = sys.stderr = log
    logging.basicConfig(stream=log, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    handle = None
    try:
        handle, first = acquire_instance(ROOT)
        if not first:
            activate_existing()
            return
        webview = ensure_window_runtime()
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('KISS.LocalAssistant')
        run_window(webview, float(os.environ.get('MYAI_DESKTOP_SMOKE_SECONDS', '0')))
    except Exception:
        logging.exception('Desktop launch failed')
        ctypes.windll.user32.MessageBoxW(None,
            'KISS could not start. Check your internet connection if this is the first launch.\n\n'
            'Details: ' + str(ROOT / 'data' / 'desktop.log'), 'KISS', 16)
    finally:
        if handle:
            kernel = ctypes.WinDLL('kernel32')
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle(handle)


if __name__ == '__main__':
    main()
