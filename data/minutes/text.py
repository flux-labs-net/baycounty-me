"""
text.py - minutes file -> text, one block per page, with OCR for scanned pages.

Most minutes before about 2022 (and most small-city minutes still) are scanned images with no text layer. Each PDF
page is read with pdftotext first; a page with almost no text is rendered (pdftoppm, 300 dpi, grayscale) and read
with Tesseract. Pages come back marked "=== Page N ===" so the model can say where each motion is.

Needs poppler-utils (pdftotext, pdftoppm, pdfinfo) and tesseract-ocr. HTML minutes (BoardDocs) are one "page".
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "meetings"))
import fetch_meetings as fm  # noqa: E402

MIN_PAGE_CHARS = 80      # fewer letters than this on a page = scanned, OCR it
OCR_DPI = 300
MAX_PAGES = 400          # a whole year of Parker minutes is about 150 pages


class ToolMissing(RuntimeError):
    pass


def _run(cmd, timeout=180):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except FileNotFoundError:
        raise ToolMissing("%s isn't installed (apt-get install poppler-utils tesseract-ocr)" % cmd[0])
    if r.returncode != 0:
        raise RuntimeError("%s: %s" % (cmd[0], r.stderr.decode("utf-8", "replace")[:200]))
    return r.stdout


def letters(s):
    return len(re.sub(r"[^A-Za-z]", "", s or ""))


def pdf_pages(path):
    out = _run(["pdfinfo", path], 60).decode("utf-8", "replace")
    m = re.search(r"^Pages:\s+(\d+)", out, re.M)
    return int(m.group(1)) if m else 0


def ocr_page(path, n, workdir):
    base = os.path.join(workdir, "p%d" % n)
    _run(["pdftoppm", "-r", str(OCR_DPI), "-gray", "-f", str(n), "-l", str(n), "-png", "-singlefile", path, base], 240)
    return _run(["tesseract", base + ".png", "-", "--psm", "6"], 240).decode("utf-8", "replace")


def pdf_text(data):
    """-> (pages [str], method 'text' | 'ocr' | 'mixed', ocr page count)."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "f.pdf")
        with open(path, "wb") as f:
            f.write(data)
        n = min(pdf_pages(path), MAX_PAGES)
        pages, ocr = [], 0
        for i in range(1, n + 1):
            t = _run(["pdftotext", "-layout", "-enc", "UTF-8", "-f", str(i), "-l", str(i), path, "-"], 120).decode("utf-8", "replace")
            if letters(t) < MIN_PAGE_CHARS:
                o = ocr_page(path, i, tmp)
                if letters(o) > letters(t):
                    t, ocr = o, ocr + 1
            pages.append(tidy(t))
    method = "ocr" if ocr and ocr == len(pages) else "mixed" if ocr else "text"
    return pages, method, ocr


def tidy(t):
    t = re.sub(r"[ \t]+\n", "\n", t.replace("\x0c", "\n"))
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def html_text(data):
    s = data.decode("utf-8", "replace")
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>|</h\d>", "\n", s)
    return tidy(fm.strip_tags(s, sep=" ").replace(" \n", "\n"))


def docx_text(data):
    """Word (.docx) minutes -> text, one paragraph per line. Page breaks aren't stored in the file, so it is one page."""
    import io
    import zipfile
    from xml.etree import ElementTree as ET
    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    lines = []
    for p in root.iter(w + "p"):
        lines.append("".join(t.text or "" for t in p.iter() if t.tag in (w + "t", w + "tab")).strip())
    return tidy("\n".join(lines))


DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def to_pages(data, ctype=""):
    """-> (pages, method, ocr pages) for a PDF, a Word file or an HTML page."""
    if data[:5] == b"%PDF-" or ctype == "application/pdf":
        return pdf_text(data)
    if ctype == DOCX or (data[:2] == b"PK" and b"word/document.xml" in data[:4000]):
        return [docx_text(data)], "text", 0
    if ctype in ("text/html", "text/plain") or data.lstrip()[:1] == b"<":
        return [html_text(data)], "text", 0
    raise ValueError("can't read %s" % (ctype or "this file type"))


def joined(pages, first=1):
    return "\n\n".join("=== Page %d ===\n%s" % (first + i, p) for i, p in enumerate(pages))


# A new meeting usually starts on a page whose first lines say so; long files are split there when they can be.
MEETING_START = re.compile(r"(?i)\b(minutes|regular meeting|special meeting|budget hearing|workshop|called to order|call to order)\b")


def chunks(pages, max_chars=90_000):
    """Split a long file into runs of whole pages under max_chars, preferring to break before a page that starts a
    new meeting. -> [(first page number, [pages])]. Most minutes are one chunk."""
    out, cur, start, size = [], [], 1, 0
    for i, p in enumerate(pages, 1):
        if cur and size + len(p) > max_chars:
            # walk back to the last page that looks like a meeting start (but keep at least half the chunk)
            cut = len(cur)
            for j in range(len(cur) - 1, len(cur) // 2, -1):
                if MEETING_START.search(cur[j][:400]):
                    cut = j
                    break
            out.append((start, cur[:cut]))
            start += cut
            cur = cur[cut:]
            size = sum(len(x) for x in cur)
        cur.append(p)
        size += len(p)
    if cur:
        out.append((start, cur))
    return out


if __name__ == "__main__":  # python3 data/minutes/text.py file.pdf  -> prints the text
    data = open(sys.argv[1], "rb").read()
    pages, method, ocr = to_pages(data)
    print(joined(pages))
    print("\n[%d pages, %s, %d OCR'd]" % (len(pages), method, ocr), file=sys.stderr)
