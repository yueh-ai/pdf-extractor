import pypdfium2 as pdfium

from pdf_extract.render import page_dir_name, render_page_to_png


def test_page_dir_name_zero_pads():
    assert page_dir_name(7) == "page_0007"


def test_render_page_to_png_creates_png(tmp_path):
    pdf_path = tmp_path / "one_page.pdf"
    doc = pdfium.PdfDocument.new()
    doc.new_page(width=100, height=100)
    doc.save(pdf_path)
    doc.close()
    out_path = tmp_path / "page.png"

    render_page_to_png(pdf_path, page_number=1, out_path=out_path)

    assert out_path.read_bytes().startswith(b"\x89PNG")
