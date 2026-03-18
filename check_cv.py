import comtypes.client, os, fitz, sys

docx_path = r"C:\Users\brans\OneDrive - University of Leeds\GraduateJobHunting\claude-cv-outputs\Epiq_Applied_AI_Systems_Engineers_20260318.docx"
pdf_path = docx_path.replace(".docx", "_check.pdf")

word = comtypes.client.CreateObject("Word.Application")
word.Visible = False
doc = word.Documents.Open(os.path.abspath(docx_path))
doc.SaveAs(os.path.abspath(pdf_path), FileFormat=17)
doc.Close()
word.Quit()

pdf = fitz.open(pdf_path)
n_pages = pdf.page_count
for i, page in enumerate(pdf):
    pix = page.get_pixmap(matrix=fitz.Matrix(150/72, 150/72))
    pix.save(rf"C:\Code\CV_crawl\cv_check_page_{i+1}.jpg")
pdf.close()
print(f"Pages: {n_pages}")
print(pdf_path)
