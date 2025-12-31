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

    words = []

    with pdfplumber.open(temp.name) as pdf:
        for page in pdf.pages:
            for w in page.extract_words(use_text_flow=True):
                t = w["text"].strip()
                if t:
                    words.append(t)

    os.unlink(temp.name)

    students = []
    seen = set()
    i = 0

    while i < len(words):
        word = words[i]

        if re.fullmatch(r"\d{7,}", word):
            seat_no = word
            name_parts = []
            gender = ""
            status = ""
            ern = ""

            for j in range(i + 1, min(i + 18, len(words))):
                w = words[j]

                if w in ("MALE", "FEMALE"):
                    gender = w

                elif w.upper() in ("REGULAR", "PRIVATE"):
                    status = w.title()

                elif re.fullmatch(r"MU\d{10,}", w):
                    ern = w

                elif re.fullmatch(r"[A-Z]{2,}", w):
                    name_parts.append(w)

            name = " ".join(name_parts).strip()

            # -------- STRICT VALIDATION --------
            if (
                seat_no not in seen
                and gender in ("MALE", "FEMALE")
                and status
                and len(name.split()) >= 2
            ):
                students.append({
                    "seat_no": seat_no,
                    "name": name,
                    "gender": gender,
                    "status": status,
                    "ern": ern
                })
                seen.add(seat_no)

            i += 18
        else:
            i += 1

    return jsonify({
        "status": "success",
        "students_found": len(students),
        "students": students
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
