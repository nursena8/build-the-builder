"""Unit tests for builder/docconv.py with hand-made office files.   python3 dev/test_docconv.py"""
import io, pathlib, sys, tempfile, unittest, zipfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "builder"))
import docconv

CT = '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>'


def make_xlsx(path):
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rel = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", CT)
        z.writestr("xl/workbook.xml", f'<workbook {ns} {rel}><sheets><sheet name="Tatiller" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/sharedStrings.xml", f'<sst {ns}><si><t>Ocak tatili</t></si><si><t>tarih</t></si></sst>')
        # style 0 general, style 1 built-in date (14), style 2 custom dd.mm.yyyy (164), style 3 custom text-ish '0.00'
        z.writestr("xl/styles.xml", f'<styleSheet {ns}><numFmts count="2"><numFmt numFmtId="164" formatCode="dd\\.mm\\.yyyy"/><numFmt numFmtId="165" formatCode="0.00"/></numFmts>'
                   '<cellXfs count="4"><xf numFmtId="0"/><xf numFmtId="14"/><xf numFmtId="164"/><xf numFmtId="165"/></cellXfs></styleSheet>')
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet {ns}><sheetData>'
                   '<row r="1"><c r="A1" t="s"><v>1</v></c><c r="B1" t="s"><v>0</v></c></row>'
                   '<row r="2"><c r="A2" s="1"><v>46321</v></c><c r="B2" t="s"><v>0</v></c></row>'      # 2026-10-26
                   '<row r="3"><c r="A3" s="2"><v>46337</v></c><c r="B3"><v>1</v></c></row>'            # 2026-11-11
                   '<row r="4"><c r="A4" s="3"><v>46321</v></c><c r="B4" s="0"><v>46321</v></c></row>'   # numbers that are not dates
                   '</sheetData></worksheet>')


def make_docx(path):
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    num = lambda n, text: f'<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="{n}"/></w:numPr></w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", CT)
        z.writestr("word/document.xml", f'<w:document {w}><w:body><w:p><w:r><w:t>Başlık</w:t></w:r></w:p>'
                   + num(1, "ilk kural") + num(1, "ikinci kural") + num(2, "başka liste") + num(1, "üçüncü kural") + '</w:body></w:document>')


class Office(unittest.TestCase):
    def test_xlsx_dates(self):
        d = pathlib.Path(tempfile.mkdtemp()); make_xlsx(d / "t.xlsx")
        sheets = docconv.xlsx_sheets(d / "t.xlsx")
        self.assertEqual(sheets[0][0], "Tatiller")
        rows = [r.split(",") for r in sheets[0][1].strip().splitlines()]
        self.assertEqual(rows[0], ["tarih", "Ocak tatili"])
        self.assertEqual(rows[1][0], "2026-10-26")      # built-in date format 14
        self.assertEqual(rows[2][0], "2026-11-11")      # custom dd.mm.yyyy
        self.assertEqual(rows[3], ["46321", "46321"])   # '0.00' and General stay numbers
    def test_docx_numbering(self):
        d = pathlib.Path(tempfile.mkdtemp()); make_docx(d / "t.docx")
        lines = docconv.docx_text(d / "t.docx").splitlines()
        self.assertEqual(lines, ["Başlık", "1. ilk kural", "2. ikinci kural", "1. başka liste", "3. üçüncü kural"])
    def test_folder_never_raises(self):
        src = pathlib.Path(tempfile.mkdtemp()); (src / "bad.docx").write_bytes(b"not a zip"); (src / "x.bin").write_bytes(b"\x00\x01")
        (src / "ok.md").write_text("tamam")
        rep = {r[0]: r[1] for r in docconv.convert_folder(src, pathlib.Path(tempfile.mkdtemp()))}
        self.assertEqual(rep, {"bad.docx": "convert_failed", "ok.md": "text", "x.bin": "copied"})


if __name__ == "__main__":
    unittest.main(verbosity=1)
