import re
import io
import pdfplumber
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

SEAT_LINE = re.compile(r"^(\d{9})\s+([A-Z ]+)\s+(MALE|FEMALE)", re.M)
RESULT_LINE = re.compile(r"\b(PASS|FAIL)\b")

SUBJECT_HEADER = re.compile(r"(\d{6})\s*:\s*([A-Za-z &()\-]+)")

def extract_text(pdf_bytes):
    text = ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += "\n" + t
    return text


def parse_subject_headers(text):
    subjects = []
    for m in SUBJECT_HEADER.finditer(text):
        subjects.append({
            "code": m.group(1),
            "name": m.group(2).strip()
        })
    return subjects


def parse_students(text, subject_headers):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    students = []
    i = 0

    while i < len(lines):
        m = SEAT_LINE.match(lines[i])
        if not m:
            i += 1
            continue

        seat_no, name, gender = m.groups()
        student = {
            "seat_no": seat_no,
            "name": name.strip(),
            "gender": gender,
            "result": None,
            "subjects": []
        }

        # Result line (next 5 lines ke andar hota hai)
        for j in range(i, min(i + 6, len(lines))):
            r = RESULT_LINE.search(lines[j])
            if r:
                student["result"] = r.group(1)
                break

        # Marks line (usually 2-3 lines neeche)
        marks_line = None
        for j in range(i + 1, i + 10):
            if j < len(lines) and re.search(r"\b\d+\s+\d+\s+\d+\s+[A-F][+]?|\b--\s+--\s+\d+", lines[j]):
                marks_line = lines[j]
                break

        if marks_line:
            cols = re.split(r"\s+", marks_line)
            idx = 0
            for sub in subject_headers:
                if idx + 3 >= len(cols):
                    break
                student["subjects"].append({
                    "code": sub["code"],
                    "name": sub["name"],
                    "internal": None if cols[idx] == "--" else int(cols[idx]),
                    "external": None if cols[idx + 1] == "--" else int(cols[idx + 1]),
                    "total": int(cols[idx + 2]),
                    "grade": cols[idx + 3]
                })
                idx += 4

        students.append(student)
        i += 1

    return students


@app.route("/parse", methods=["POST"])
def parse_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400

    pdf_bytes = request.files["file"].read()
    text = extract_text(pdf_bytes)
    subject_headers = parse_subject_headers(text)
    students = parse_students(text, subject_headers)

    return jsonify({
        "status": "success",
        "students_found": len(students),
        "students": students
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
