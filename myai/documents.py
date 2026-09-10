"""Local extraction with explicit unsupported states and server-owned filenames."""
import json

TEXT = {'.py', '.js', '.ts', '.html', '.css', '.json', '.md', '.txt', '.csv'}


def extract(path):
    if path.suffix.lower() in TEXT:
        if path.stat().st_size > 200_000:
            return {'status': 'stored_only', 'detail': 'Text exceeds 200 KB. Attach a smaller excerpt.', 'passages': []}
        try:
            content = path.read_text(encoding='utf-8')
            if '\x00' in content:
                raise UnicodeError()
            return {'status': 'ready', 'detail': 'Text extracted locally', 'passages': [{'page': None, 'text': content}]}
        except UnicodeError:
            return {'status': 'stored_only', 'detail': 'Not UTF-8 text', 'passages': []}
    if path.suffix.lower() == '.pdf':
        try:
            from pypdf import PdfReader
        except ImportError:
            return {'status': 'stored_only', 'detail': 'PDF reading needs pypdf. Run scripts/setup_local.py.', 'passages': []}
        try:
            reader = PdfReader(path)
            if reader.is_encrypted:
                raise ValueError('Encrypted PDF; unlock a copy before attaching.')
            if len(reader.pages) > 200:
                raise ValueError('PDF exceeds 200 pages. Attach the relevant pages.')
            passages = []
            total = 0
            for number, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ''
                total += len(text)
                if total > 200_000:
                    raise ValueError('PDF text exceeds the extraction budget. Attach a shorter document.')
                if text.strip():
                    passages.append({'page': number, 'text': text})
            if not passages:
                raise ValueError('No text found. This PDF needs OCR; OCR is not installed in this release.')
            return {'status': 'ready', 'detail': f'Text extracted from {len(passages)} pages', 'passages': passages}
        except Exception as exc:
            return {'status': 'stored_only', 'detail': str(exc)[:250], 'passages': []}
    return {'status': 'stored_only', 'detail': 'Stored for download. Image understanding is not enabled in chat.', 'passages': []}


def context(uploader, uploads, query):
    if not isinstance(uploads, list) or len(uploads) > 12:
        raise ValueError('Attach up to 12 documents.')
    words = set(query.lower().split())
    records, warnings = [], []
    for item in uploads:
        ident = item.get('id') if isinstance(item, dict) else item
        metadata = uploader.metadata(ident)
        extraction = metadata.get('extraction', {})
        if extraction.get('status') != 'ready':
            warnings.append(metadata['filename'] + ': ' + extraction.get('detail', 'Stored only'))
            continue
        for passage in extraction['passages']:
            text = passage['text']
            for offset in range(0, len(text), 2000):
                chunk = text[offset:offset + 2000]
                score = len(words.intersection(chunk.lower().split()))
                records.append((score, metadata['filename'], passage['page'], chunk))
    records.sort(key=lambda x: -x[0])
    passages = [{'source': name, 'page': page, 'text': chunk} for _, name, page, chunk in records[:6]]
    return json.dumps({'passages': passages, 'unread_attachments': warnings}, ensure_ascii=False)
