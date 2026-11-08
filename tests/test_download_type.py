"""A PDF (or Office file) from Telegram is saved with its real type and .pdf name, never as .bin."""
import unittest
from pathlib import Path

from unified import Blob, download_mime


class Headers:
    def __init__(self): self.sent = {}
    def send_header(self, k, v): self.sent[k] = v


class DownloadTypeTests(unittest.TestCase):
    def test_pdf_bytes_keep_pdf_type_even_when_declared_octet_stream(self):
        self.assertEqual(download_mime('application/pdf', 'application/octet-stream', 'wizardos-desktop-phone-v3-2026-11-05.pdf'), 'application/pdf')

    def test_unknown_bytes_use_declared_or_named_type_only_from_the_safe_list(self):
        self.assertEqual(download_mime('application/octet-stream', 'application/pdf', 'a.pdf'), 'application/pdf')
        self.assertEqual(download_mime(None, 'application/octet-stream', 'a.pdf'), 'application/pdf')
        self.assertEqual(download_mime('application/octet-stream', 'text/html', 'a.html'), 'application/octet-stream')
        self.assertEqual(download_mime('application/octet-stream', 'image/svg+xml', 'a.svg'), 'application/octet-stream')
        self.assertEqual(download_mime('text/html', 'text/html', 'a.pdf'), 'application/octet-stream')

    def test_office_files_are_zip_by_bytes_but_keep_their_office_type(self):
        docx = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        self.assertEqual(download_mime('application/zip', 'application/octet-stream', 'brief.docx'), docx)
        self.assertEqual(download_mime('application/zip', 'text/html', 'x.html'), 'application/zip')


if __name__ == '__main__':
    unittest.main()
