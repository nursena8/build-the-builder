"""Turn a folder of bank documents into text the builder can read. Standard library only. Never raises on a bad file.

    convert_folder(src_dir, dst_dir) -> list of (relative path, status, note)

Copies every file to dst_dir (same relative path) and writes a `.txt` (or one `.csv` per sheet) next to documents that are not plain text:
  .docx  -> text of word/document.xml (paragraphs, table rows with ' | ')
  .xlsx  -> one CSV per sheet (shared strings resolved)
  .md .txt .csv .json .html .xml .yaml .yml -> copied as they are
  .pdf   -> text from `pdftotext` or macOS `textutil`/`mdls` is not available for PDFs, so the file is copied unchanged and the
            builder reads it with its Read tool (it reads PDFs)
Anything else is copied and reported as 'copied'.
"""
import csv, io, pathlib, re, shutil, subprocess, zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
TEXT = {".md", ".txt", ".csv", ".json", ".html", ".htm", ".xml", ".yaml", ".yml", ".tsv"}


def docx_text(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    out = []
    def para(p):
        parts = []
        for n in p.iter():
            if n.tag == W + "t": parts.append(n.text or "")
            elif n.tag in (W + "tab",): parts.append("\t")
            elif n.tag in (W + "br", W + "cr"): parts.append("\n")
        return "".join(parts)
    counters = {}
    def numbered(p):
        """'3. ' for a paragraph in a Word auto-numbered list (the number is not stored as text)."""
        ppr = p.find(W + "pPr")
        npr = ppr.find(W + "numPr") if ppr is not None else None
        if npr is None: return ""
        nid = npr.find(W + "numId"); lvl = npr.find(W + "ilvl")
        key = (nid.get(W + "val") if nid is not None else "0", lvl.get(W + "val") if lvl is not None else "0")
        if key[0] == "0": return ""
        counters[key] = counters.get(key, 0) + 1
        return str(counters[key]) + ". "
    body = root.find(W + "body")
    for el in (body if body is not None else []):
        if el.tag == W + "p":
            out.append(numbered(el) + para(el))
        elif el.tag == W + "tbl":
            for tr in el.iter(W + "tr"):
                out.append(" | ".join(" ".join(para(p) for p in tc.iter(W + "p")).strip() for tc in tr.findall(W + "tc")))
            out.append("")
    return "\n".join(out)


_BUILTIN_DATE = set(range(14, 23)) | set(range(27, 37)) | set(range(45, 48)) | set(range(50, 59))


def _date_styles(z):
    """Indexes of cell styles (the `s` attribute of a cell) whose number format is a date or time."""
    if "xl/styles.xml" not in z.namelist(): return set()
    root = ET.fromstring(z.read("xl/styles.xml"))
    custom = {}
    for nf in root.iter(S + "numFmt"):
        code = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', "", nf.get("formatCode") or "")
        custom[int(nf.get("numFmtId"))] = bool(re.search(r"[dmyhs]", code, re.I))
    out = set()
    xfs = root.find(S + "cellXfs")
    for i, xf in enumerate(xfs if xfs is not None else []):
        fid = int(xf.get("numFmtId") or 0)
        if fid in _BUILTIN_DATE or custom.get(fid): out.add(i)
    return out


def _excel_date(v):
    import datetime
    try:
        x = float(v)
        d = datetime.datetime(1899, 12, 30) + datetime.timedelta(days=x)
        return d.strftime("%Y-%m-%d") if abs(x - int(x)) < 1e-9 else d.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return v


def xlsx_sheets(path):
    """Return [(sheet name, csv text)]."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        shared = []
        if "xl/sharedStrings.xml" in names:
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(S + "si"):
                shared.append("".join(t.text or "" for t in si.iter(S + "t")))
        datestyles = _date_styles(z)
        titles = {}
        rels = {}
        if "xl/workbook.xml" in names:
            wb = ET.fromstring(z.read("xl/workbook.xml"))
            for sh in wb.iter(S + "sheet"):
                titles[sh.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")] = sh.get("name")
        if "xl/_rels/workbook.xml.rels" in names:
            for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")):
                rels[r.get("Id")] = r.get("Target")
        order = []
        for rid, name in titles.items():
            t = rels.get(rid) or ""
            t = t.lstrip("/"); t = t if t.startswith("xl/") else "xl/" + t
            order.append((name, t))
        if not order:
            order = [(f"sheet{i + 1}", n) for i, n in enumerate(sorted(x for x in names if x.startswith("xl/worksheets/sheet")))]
        res = []
        for name, member in order:
            if member not in names: continue
            rows = []
            for row in ET.fromstring(z.read(member)).iter(S + "row"):
                cells = {}
                for c in row.findall(S + "c"):
                    ref = c.get("r") or ""
                    col = 0
                    for ch in re.match(r"[A-Z]*", ref).group(0): col = col * 26 + (ord(ch) - 64)
                    t = c.get("t"); v = c.find(S + "v")
                    if t == "s" and v is not None and (v.text or "").isdigit() and int(v.text) < len(shared): val = shared[int(v.text)]
                    elif t == "inlineStr": val = "".join(x.text or "" for x in c.iter(S + "t"))
                    else:
                        val = v.text if v is not None and v.text is not None else ""
                        if val != "" and t in (None, "n") and (c.get("s") or "").isdigit() and int(c.get("s")) in datestyles: val = _excel_date(val)
                    cells[col] = val
                if cells:
                    rows.append([cells.get(i, "") for i in range(1, max(cells) + 1)])
            buf = io.StringIO(); csv.writer(buf).writerows(rows)
            res.append((name, buf.getvalue()))
        return res


def pdf_text(path):
    """Text from `pdftotext` when it is installed, else None."""
    exe = shutil.which("pdftotext")
    if not exe: return None
    try:
        r = subprocess.run([exe, "-layout", str(path), "-"], capture_output=True, text=True, timeout=60)
        return r.stdout if r.returncode == 0 and r.stdout.strip() else None
    except Exception:
        return None


def safe_name(s):
    return re.sub(r"[^\w.\-]+", "_", s, flags=re.UNICODE).strip("_") or "sheet"


def convert_folder(src, dst):
    src, dst = pathlib.Path(src), pathlib.Path(dst)
    report = []
    for f in sorted(src.rglob("*")):
        if not f.is_file() or f.name.startswith(".") or f.name.startswith("~$"): continue
        rel = f.relative_to(src)
        target = dst / rel
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(f, target)
        except Exception as e:
            report.append((str(rel), "copy_failed", str(e)[:100])); continue
        ext = f.suffix.lower()
        try:
            if ext in TEXT:
                report.append((str(rel), "text", ""))
            elif ext == ".docx":
                t = docx_text(f); target.with_name(target.name + ".txt").write_text(t, encoding="utf-8")
                report.append((str(rel), "converted", f"{len(t)} chars"))
            elif ext in (".xlsx", ".xlsm"):
                sheets = xlsx_sheets(f)
                for name, text in sheets:
                    target.with_name(f"{target.name}.{safe_name(name)}.csv").write_text(text, encoding="utf-8")
                report.append((str(rel), "converted", f"{len(sheets)} sheet(s)"))
            elif ext == ".pdf":
                t = pdf_text(f)
                if t:
                    target.with_name(target.name + ".txt").write_text(t, encoding="utf-8"); report.append((str(rel), "converted", f"{len(t)} chars"))
                else:
                    report.append((str(rel), "pdf", "read it with the Read tool"))
            else:
                report.append((str(rel), "copied", "unknown type; open it with the tool that fits"))
        except Exception as e:
            report.append((str(rel), "convert_failed", str(e)[:100]))
    return report
