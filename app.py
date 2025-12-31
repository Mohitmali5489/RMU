from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import tempfile
import os
import re

app = Flask(__name__)
CORS(app)  # Allow GitHub Pages / Railway frontend

@app.route("/parse", methods=["POST"])
def parse_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]

    # Save PDF temporarily
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    file.save(temp.name)

    full_text = ""

    # Extract ALL text from ALL pages
    with pdfplumber.open(temp.name) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += "\n" + text

    os.unlink(temp.name)

    lines = full_text.splitlines()
    students = []
    seen_seats = set()

    # ------------------------------------------------
    # STEP 1: Extract SEAT NO + NAME (CORRECT METHOD)
    # ------------------------------------------------
    for line in lines:
        line = re.sub(r"\s+", " ", line).strip()

        # Matches:
        # 262112705 MOHIT BHARAT MALI
        match = re.match(r"^(\d{7,})\s+([A-Z][A-Z\s]{3,})$", line)

        if match:
            seat_no = match.group(1)
            name = match.group(2).strip()

            # Avoid duplicates
            if seat_no not in seen_seats:
                students.append({
                    "seat_no": seat_no,
                    "name": name,
                    "ern": "",
                    "gender": ""
                })
                seen_seats.add(seat_no)

    # ------------------------------------------------
    # STEP 2: Attach ERN + GENDER per student
    # ------------------------------------------------
    for student in students:
        pattern = (
            student["seat_no"]
            + r".*?(MU\d{10,}).*?\b(MALE|FEMALE)\b"
        )

        m = re.search(pattern, full_text, re.S)
        if m:
            student["ern"] = m.group(1)
            student["gender"] = m.group(2)

    return jsonify({
        "status": "success",
        "students_found": len(students),
        "students": students
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
