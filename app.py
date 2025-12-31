from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import tempfile
import os
import re

app = Flask(__name__)
CORS(app)

@app.route("/parse", methods=["POST"])
def parse_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    file.save(temp.name)

    lines = []

    # ---- Extract text line-by-line ----
    with pdfplumber.open(temp.name) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                for l in text.splitlines():
                    clean = re.sub(r"\s+", " ", l).strip()
                    if clean:
                        lines.append(clean)

    os.unlink(temp.name)

    students = []
    seen = set()

    i = 0
    while i < len(lines):
        line = lines[i]

        # Seat number = standalone 7+ digit number
        if re.fullmatch(r"\d{7,}", line):
            seat_no = line

            name = ""
            gender = ""
            ern = ""
            status = ""

            # Look ahead safely
            for j in range(i + 1, min(i + 8, len(lines))):
                l = lines[j]

                if not name and re.fullmatch(r"[A-Z][A-Z\s]{3,}", l):
                    name = l

                if not gender and l in ("MALE", "FEMALE"):
                    gender = l

                if not ern and re.match(r"MU\d{10,}", l):
                    ern = l

                if not status and l.upper() in ("REGULAR", "PRIVATE"):
                    status = l.title()

            if seat_no not in seen and name:
                students.append({
                    "seat_no": seat_no,
                    "name": name,
                    "status": status,
                    "gender": gender,
                    "ern": ern
                })
                seen.add(seat_no)

        i += 1

    return jsonify({
        "status": "success",
        "students_found": len(students),
        "students": students
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
