from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "MU Result Parser API running on Railway"

@app.route("/parse", methods=["POST"])
def parse_pdf():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"})

        file = request.files["file"]
        pages_info = []

        with pdfplumber.open(file) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                pages_info.append({
                    "page": i + 1,
                    "has_text": bool(text),
                    "char_count": len(text) if text else 0
                })

        return jsonify({
            "status": "ok",
            "total_pages": len(pages_info),
            "pages": pages_info
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })
