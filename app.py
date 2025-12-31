from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import re
import tempfile
import os

app = Flask(__name__)
CORS(app)

# -------------------------------
# PDF TEXT EXTRACTION
# -------------------------------
def extract_text_from_pdf(pdf_path):
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            txt = page.extract_text()
            if txt:
                full_text += "\n" + txt
    return full_text


# -------------------------------
# STUDENT PARSER (ROBUST)
# -------------------------------
def extract_students_from_text(text):
    students = []

    # 🔒 Start from FIRST real student row
    start_match = re.search(r"\n\d{7,8}\s+[A-Z]{2,}\s+[A-Z]{2,}", text)
    if not start_match:
        return students

    text = text[start_match.start():]

    # Split per student
    blocks = re.split(r"\n(?=\d{7,8}\s+[A-Z]{2,}\s+[A-Z]{2,})", text)

    for block in blocks:
        block = block.strip()

        # Skip noise / subject headers
        if ":" in block and "MU-" not in block:
            continue

        # Seat No + Name
        m = re.match(r"^(\d{7,8})\s+([A-Z]{2,}(?:\s+[A-Z]{2,})+)", block)
        if not m:
            continue

        seat_no = m.group(1)
        name = m.group(2)

        gender = (
            "MALE" if " MALE " in block else
            "FEMALE" if " FEMALE " in block else None
        )

        status = "Regular" if " Regular " in block else None
        result = (
            "PASS" if " PASS " in block else
            "FAIL" if " FAIL " in block else None
        )

        tm = re.search(r"MARKS\s*\(?(\d+)\)?", block)
        total_marks = int(tm.group(1)) if tm else None

        sg = re.search(r"SGPA[:\s]+([\d.]+)", block)
        sgpa = float(sg.group(1)) if sg else None

        col = re.search(r"MU-\d+:(.+)", block)
        college = col.group(1).strip() if col else None

        students.append({
            "seat_no": seat_no,
            "name": name,
            "gender": gender,
            "status": status,
            "college": college,
            "result": result,
            "total_marks": total_marks,
            "sgpa": sgpa,
            "subjects": []   # ← ready for per-subject marks
        })

    return students


# -------------------------------
# API ROUTE
# -------------------------------
@app.route("/parse", methods=["POST"])
def parse_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    pdf_file = request.files["file"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf_file.save(tmp.name)
        pdf_path = tmp.name

    try:
        text = extract_text_from_pdf(pdf_path)
        students = extract_students_from_text(text)

        return jsonify({
            "status": "success",
            "students_found": len(students),
            "students": students
        })

    finally:
        os.remove(pdf_path)


# -------------------------------
# ENTRY POINT (Railway)
# -------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
