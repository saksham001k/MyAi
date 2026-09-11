import json
import tempfile
import unittest
from pathlib import Path

from myai.documents import DocumentLibrary, extract_pdf, passage_supports


def simple_pdf(pages):
    objects = ["%PDF-1.4"]
    objects.append("1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj")
    kids = " ".join(f"{3 + i} 0 R" for i in range(len(pages)))
    objects.append(f"2 0 obj << /Type /Pages /Kids [{kids}] /Count {len(pages)} >> endobj")
    next_id = 3 + len(pages)
    for i, text in enumerate(pages):
        content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
        page_id = 3 + i
        stream_id = next_id
        next_id += 1
        objects.append(
            f"{page_id} 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {stream_id} 0 R /Resources << /Font << /F1 {next_id} 0 R >> >> >> endobj"
        )
        objects.append(
            f"{stream_id} 0 obj << /Length {len(content)} >> stream\n{content}\nendstream endobj"
        )
    objects.append(f"{next_id} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj")
    objects.append("trailer << /Root 1 0 R >>\n%%EOF")
    return "\n".join(objects).encode("latin-1")


class DocumentTests(unittest.TestCase):
    def test_pdf_and_text_retrieval_with_page_citation(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = DocumentLibrary(Path(tmp))
            lib.ingest("notes.txt", b"GGUF models belong in the models folder of the workspace.")
            lib.ingest("guide.pdf", simple_pdf(["Loopback-only API binds to 127.0.0.1.", "Keep licenses with the runtime."]))
            hits = lib.search("models folder")
            self.assertTrue(hits)
            self.assertEqual(hits[0]["source"], "notes.txt")
            self.assertEqual(hits[0]["page"], 1)
            pdf_hits = lib.search("loopback")
            self.assertEqual(pdf_hits[0]["page"], 1)
            self.assertIn("127.0.0.1", pdf_hits[0]["text"])

    def test_eval_set_passages_support_expected_facts(self):
        fixture = json.loads(
            (Path(__file__).resolve().parent / "fixtures" / "rag_eval.json").read_text()
        )
        with tempfile.TemporaryDirectory() as tmp:
            lib = DocumentLibrary(Path(tmp))
            for case in fixture["cases"]:
                lib.ingest(case["document"], case["content"].encode())
                hits = lib.search(case["question"], limit=3)
                self.assertTrue(hits, case["id"])
                self.assertTrue(
                    any(case["expected_contains"].lower() in hit["text"].lower() for hit in hits),
                    case["id"],
                )
                self.assertTrue(passage_supports(case["expected_contains"], hits), case["id"])

    def test_rejects_non_pdf_header(self):
        with self.assertRaises(ValueError):
            extract_pdf(b"<html>not a pdf</html>")


if __name__ == "__main__":
    unittest.main()
