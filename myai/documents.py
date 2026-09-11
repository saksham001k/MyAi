"""Local PDF/text extraction and lexical retrieval with passage citations."""
from __future__ import annotations

import json
import os
import re
import uuid
import zlib
from pathlib import Path, PurePosixPath

MAX_DOCUMENT = 8 * 1024 * 1024
MAX_LIBRARY = 50
PASSAGE_CHARS = 800


def _safe_name(name):
    if not isinstance(name, str) or len(name) > 180 or "\\" in name or "/" in name:
        raise ValueError("Use a plain document filename")
    if name in {".", ".."} or name.startswith("."):
        raise ValueError("Hidden document names are not allowed")
    return PurePosixPath(name).name


def extract_text_file(data, name="document.txt"):
    text = data.decode("utf-8")
    if "\x00" in text:
        raise ValueError("Binary files are not supported")
    return [{"page": 1, "text": text, "source": name}]


def _pdf_unescape(payload):
    payload = payload.replace("\\n", "\n").replace("\\r", "\n").replace("\\t", "\t")
    payload = payload.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")
    return payload


def _pdf_strings(content):
    texts = []
    for match in re.finditer(rb"\((?:\\.|[^\\)])*\)\s*Tj", content):
        inner = match.group(0)[1:match.group(0).rfind(b")")]
        texts.append(_pdf_unescape(inner.decode("latin-1", errors="ignore")))
    for match in re.finditer(rb"\[(.*?)\]\s*TJ", content, re.S):
        for piece in re.finditer(rb"\((?:\\.|[^\\)])*\)", match.group(1)):
            inner = piece.group(0)[1:-1]
            texts.append(_pdf_unescape(inner.decode("latin-1", errors="ignore")))
    return texts


def extract_pdf(data, name="document.pdf"):
    if not data.startswith(b"%PDF"):
        raise ValueError("File is not a PDF")
    if len(data) > MAX_DOCUMENT:
        raise ValueError("PDF is larger than 8 MiB")
    pages = []
    # Split on page objects so citations can carry a page number for simple files.
    page_starts = [m.start() for m in re.finditer(rb"/Type\s*/Page(?![sA-Za-z])", data)]
    spans = page_starts + [len(data)]
    if len(page_starts) < 1:
        page_starts, spans = [0], [0, len(data)]
    for index, start in enumerate(page_starts, start=1):
        chunk = data[start:spans[index]]
        pieces = []
        for stream in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", chunk, re.S):
            payload = stream.group(1)
            if re.search(rb"/Filter\s*/FlateDecode", chunk[max(0, stream.start() - 200):stream.start()]):
                try:
                    payload = zlib.decompress(payload)
                except zlib.error:
                    continue
            pieces.extend(_pdf_strings(payload))
        text = "\n".join(part.strip() for part in pieces if part.strip())
        if text:
            pages.append({"page": index, "text": text, "source": name})
    if not pages:
        raise ValueError("No extractable text was found. Scanned or compressed PDFs are not supported.")
    return pages


def chunk_pages(pages, size=PASSAGE_CHARS):
    passages = []
    for page in pages:
        text = re.sub(r"\s+", " ", page["text"]).strip()
        offset = 0
        while offset < len(text):
            piece = text[offset:offset + size]
            if len(piece) == size:
                cut = piece.rfind(" ")
                if cut > size // 2:
                    piece = piece[:cut]
            piece = piece.strip()
            if piece:
                passages.append({
                    "id": f"{page['source']}:p{page['page']}:{offset}",
                    "source": page["source"],
                    "page": page["page"],
                    "text": piece,
                })
            offset += max(len(piece), 1)
    return passages


def _tokens(text):
    return re.findall(r"[A-Za-z0-9]{2,}", text.lower())


def retrieve(passages, query, limit=5):
    query_tokens = _tokens(query)
    if not query_tokens or not passages:
        return []
    df = {}
    for passage in passages:
        for token in set(_tokens(passage["text"])):
            df[token] = df.get(token, 0) + 1
    scored = []
    n = len(passages)
    for passage in passages:
        tf = {}
        words = _tokens(passage["text"])
        for token in words:
            tf[token] = tf.get(token, 0) + 1
        score = 0.0
        for token in query_tokens:
            if token not in tf:
                continue
            idf = (n + 1) / (df.get(token, 0) + 1)
            score += (tf[token] / len(words)) * idf
        if score > 0:
            item = dict(passage)
            item["score"] = round(score, 4)
            scored.append(item)
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]


def passage_supports(answer, passages):
    """Lexical overlap check used by the fixed evaluation set — not an LLM judge."""
    answer_tokens = set(_tokens(answer))
    if not answer_tokens:
        return False
    for passage in passages:
        overlap = answer_tokens & set(_tokens(passage["text"]))
        if len(overlap) >= max(2, len(answer_tokens) // 6):
            return True
    return False


class DocumentLibrary:
    def __init__(self, root):
        self.root = Path(root) / "data" / "documents"
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"
        if not self.index_path.exists():
            self._write({"documents": []})

    def _write(self, payload):
        temp = self.index_path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(temp, self.index_path)

    def _index(self):
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"documents": []}

    def list(self):
        return self._index()["documents"]

    def ingest(self, name, data):
        name = _safe_name(name)
        if not isinstance(data, (bytes, bytearray)):
            raise ValueError("Document bytes are required")
        if len(data) > MAX_DOCUMENT:
            raise ValueError("Document is larger than 8 MiB")
        index = self._index()
        if len(index["documents"]) >= MAX_LIBRARY:
            raise ValueError("Document library limit is 50 files")
        suffix = Path(name).suffix.lower()
        if suffix in {".txt", ".md"}:
            pages = extract_text_file(data, name)
        elif suffix == ".pdf":
            pages = extract_pdf(bytes(data), name)
        else:
            raise ValueError("Supported documents are .txt, .md, and text-based .pdf")
        ident = uuid.uuid4().hex
        folder = self.root / ident
        folder.mkdir()
        source = folder / name
        source.write_bytes(data)
        passages = chunk_pages(pages)
        record = {
            "id": ident,
            "name": name,
            "bytes": len(data),
            "pages": len(pages),
            "passages": len(passages),
        }
        (folder / "passages.json").write_text(json.dumps(passages), encoding="utf-8")
        index["documents"].append(record)
        self._write(index)
        return record

    def passages(self, document_id=None):
        items = []
        for record in self.list():
            if document_id and record["id"] != document_id:
                continue
            path = self.root / record["id"] / "passages.json"
            try:
                items.extend(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        return items

    def search(self, query, limit=5):
        return retrieve(self.passages(), query, limit=limit)
