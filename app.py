from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import re
import tempfile
import os

app = Flask(__name__)
CORS(app)  # allow GitHub Pages / Railway frontend

@app.route("/parse", methods=["POST"])
def parse_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]

    # Save temp PDF
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    file.save(temp.name)

    full_text = ""

    with pdfplumber.open(temp.name) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += "\n" + text

    os.unlink(temp.name)

    # ---------- STUDENT PARSING ----------
    students = []

    blocks = re.split(r"\bSEAT NO\b", full_text)

    for block in blocks[1:]:  # skip header
        seat = re.search(r"(\d{6,})", block)
        name = re.search(r"NAME\s*:\s*([A-Z\s]+)", block)
        ern = re.search(r"(MU\d+)", block)
        gender = re.search(r"\b(MALE|FEMALE)\b", block)

        students.append({
            "seat_no": seat.group(1) if seat else "",
            "name": name.group(1).strip() if name else "",
            "ern": ern.group(1) if ern else "",
            "gender": gender.group(1) if gender else ""
        })

    return jsonify({
        "status": "success",
        "students_found": len(students),
        "students": students
    })
