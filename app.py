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

    full_text = ""

    with pdfplumber.open(temp.name) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                full_text += "\n" + t

    os.unlink(temp.name)

    students = []
    seen = set()

    for line in full_text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()

        # Matches:
        # 262112705 MOHIT BHARAT MALI Regular MALE MU0341...
        m = re.match(
            r"^(\d{7,})\s+([A-Z][A-Z\s]+?)\s+(Regular|PRIVATE)\s+(MALE|FEMALE)\s+(MU\d+)",
            line
        )

        if m:
            seat_no = m.group(1)
            name = m.group(2).strip()
            status = m.group(3)
            gender = m.group(4)
            ern = m.group(5)

            if seat_no not in seen:
                students.append({
                    "seat_no": seat_no,
                    "name": name,
                    "status": status,
                    "gender": gender,
                    "ern": ern
                })
                seen.add(seat_no)

    return jsonify({
        "status": "success",
        "students_found": len(students),
        "students": students
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
