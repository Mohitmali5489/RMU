from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import tempfile
import os

app = Flask(__name__)
CORS(app)

@app.route("/parse", methods=["POST"])
def parse_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        file.save(tmp.name)
        pdf_path = tmp.name

    pages_data = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages_data.append({
                "page": i,
                "char_count": len(text),
                "has_text": bool(text.strip()),
                "text": text
            })

    os.remove(pdf_path)

    return jsonify({
        "status": "ok",
        "total_pages": len(pages_data),
        "pages": pages_data
    })
