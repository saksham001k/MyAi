"""Create standalone HTML outputs only for an explicit Desktop request."""
import os
import re
import uuid
from pathlib import Path
from .agent import AgentStopped


def desktop_directory():
    if os.name == 'nt':
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as key:
            value, _ = winreg.QueryValueEx(key, 'Desktop')
        result = Path(os.path.expandvars(value))
    else:
        result = Path.home() / 'Desktop'
    if not result.is_dir():
        raise ValueError('Your Desktop folder could not be found.')
    return result


def wants_desktop_html(prompt):
    text = prompt.lower().strip()
    if re.search(r'^(?:how\b|explain\b|what\b|why\b|tell me how\b)', text):
        return False
    if re.search(r'\b(?:do not|don.t|never)\s+(?:create|make|build|save|write|generate)\b', text):
        return False
    return bool(re.search(r'\b(?:build|create|make|save|write|generate)\b', text) and
                re.search(r'\bdesktop\b', text) and re.search(r'\bhtml\b|\.html\b', text))


def extract_html(answer):
    # Models may wrap output in prose or a single Markdown fence.
    matches = list(re.finditer(r'<!doctype\s+html\b[^>]*>|<html\b[^>]*>', answer, re.I))
    if not matches:
        raise ValueError('Model returned an explanation instead of a complete HTML file. Retry the request.')
    start = matches[0].start()
    end = re.search(r'</html\s*>', answer[start:], re.I)
    if not end:
        raise ValueError('Model output is incomplete; no Desktop file was saved.')
    html = answer[start:start + end.end()]
    if '\x00' in html or len(html.encode('utf-8')) > 200_000:
        raise ValueError('Generated HTML exceeds the file budget.')
    if not re.search(r'<body\b', html, re.I):
        raise ValueError('Generated HTML has no body.')
    if re.search(r'<(?:script|link)\b[^>]*\b(?:src|href)\s*=', html, re.I):
        raise ValueError('Model referenced separate files. Retry for one self-contained HTML file.')
    return html


def basic_calculator_request(goal):
    text = goal.lower()
    # Only the common plain calculator request uses this specific template.
    return bool(re.search(r'\bcalculator\b', text) and
                not re.search(r'\b(?:scientific|graphing|mortgage|loan|tax|currency|bmi|age|custom|sin|cos|log|percent)\b', text))


def create_html(engine, goal, cancel, draft, progress=None):
    if basic_calculator_request(goal):
        if cancel.is_set():
            raise AgentStopped('File creation cancelled.')
        html = (Path(__file__).parent / 'templates/calculator.html').read_text(encoding='utf-8')
        return publish_html(html, goal, cancel, draft)
    messages = [
        {'role': 'system', 'content': 'You create working standalone HTML apps. /no_think '
         'Return ONLY a complete HTML document with inline CSS and JavaScript. No explanation. '
         'Use no external resources, libraries or other files. The application saves the file; '
         'you must not claim you saved or tested it. Make a usable interface and handle invalid input. '
         'For calculators include decimals, clear, backspace, keyboard input and division-by-zero handling. '
         'Do not use eval or Function to calculate.'},
        {'role': 'user', 'content': goal}]
    tokens = max(512, min(4096, getattr(engine, 'context', 4096) - 768))
    parts, size = [], 0
    stream = engine.stream(messages, temperature=0.15, max_tokens=tokens)
    try:
        for token in stream:
            if cancel.is_set():
                raise AgentStopped('File creation cancelled.')
            size += len(token.encode('utf-8'))
            if size > 200_000:
                raise ValueError('Model output exceeds the file budget.')
            parts.append(token)
            if progress:
                progress(size)
    finally:
        close = getattr(stream, 'close', None)
        if close:
            close()
    if cancel.is_set():
        raise AgentStopped('File creation cancelled.')
    event = getattr(engine, 'last_llama_event', None) or {}
    if not any(c.get('finish_reason') == 'stop' for c in event.get('choices', [])):
        raise ValueError('Model did not finish the HTML document. Increase context and retry; no Desktop file was saved.')
    html = extract_html(''.join(parts))
    return publish_html(html, goal, cancel, draft)


def publish_html(html, goal, cancel, draft):
    draft.write_text(html, encoding='utf-8')
    desktop = desktop_directory()
    requested = re.search(r'\b([a-zA-Z0-9][a-zA-Z0-9_-]{0,60})\.html\b', goal, re.I)
    name = requested.group(1) if requested else 'calculator' if 'calculator' in goal.lower() else 'myai-app'
    target = desktop / (name + '.html')
    # Write privately, then publish atomically; existing Desktop files are preserved.
    temp = desktop / ('.myai-' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('x', encoding='utf-8', newline='') as file:
            file.write(html)
            file.flush()
            os.fsync(file.fileno())
        if cancel.is_set():
            raise AgentStopped('File creation cancelled.')
        try:
            os.link(temp, target)
        except FileExistsError:
            target = desktop / (name + '-' + uuid.uuid4().hex[:8] + '.html')
            os.link(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    return target
