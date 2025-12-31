import re
import io
import pdfplumber
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# -------------------------
# REGEX PATTERNS
# -------------------------

SEAT_NAME_PATTERN = re.compile(
    r"(?P<seat>\d{9})\s+(?P<name>[A-Z ]{5,})"
)

GENDER_PATTERN = re.compile(r"\b(MALE|FEMALE)\b")
RESULT_PATTERN = re.compile(r"\b(PASS|FAIL)\b")
SGPA_PATTERN = re.compile(r"SGPA\s*[:\-]?\s*(\d+\.\d+)")
TOTAL_PATTERN = re.compile(r"MARKS\s*\(?(\d+)\)?")

SUBJECT_HEADER_PATTERN = re.compile(
    r"(?P<code>\d{6})\s*:\s*(?P<name>[A-Za-z &()\-]+)"
)

MARKS_ROW_PATTERN = re.compile(
    r"\b(\d{1,2}|--)\s+(\d{1,2}|--)\s+(\d{2,3})\s+([A-FP][+]?)"
)

# -------------------------
# HELPERS
# -------------------------

def extract_subject_headers(full_text):
    headers = []
    for m in SUBJECT_HEADER_PATTERN.finditer(full_text):
        headers.append({
            "code": m.group("code"),
            "name": m.group("name").strip()
        })
    return headers


def extract_students_blocks(text):
    positions = [(m.start(), m.group()) for m in SEAT_NAME_PATTERN.finditer(text)]
    blocks = []

    for i in range(len(positions)):
        start = positions[i][0]
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        blocks.append(text[start:end])

    return blocks


def parse_student_block(block, subject_headers):
    seat_match = SEAT_NAME_PATTERN.search(block)
    if not seat_match:
        return None

    seat_no = seat_match.group("seat")
    name = seat_match.group("name").strip()

    gender = None
    g = GENDER_PATTERN.search(block)
    if g:
        gender = g.group(1)

    result = None
    r = RESULT_PATTERN.search(block)
    if r:
        result = r.group(1)

    sgpa = None
    s = SGPA_PATTERN.search(block)
    if s:
        sgpa = float(s.group(1))

    total_marks = None
    t = TOTAL_PATTERN.search(block)
    if t:
        total_marks = int(t.group(1))

    # ---- SUBJECTS ----
    subjects = []
    marks_rows = MARKS_ROW_PATTERN.findall(block)

    for i, header in enumerate(subject_headers):
        if i >= len(marks_rows):
            continue

        internal, external, total, grade = marks_rows[i]

        subjects.append({
            "code": header["code"],
            "name": header["name"],
            "internal": None if internal == "--" else int(internal),
            "external": None if external == "--" else int(external),
            "total": int(total),
            "grade": grade
        })

    return {
        "seat_no": seat_no,
        "name": name,
        "gender": gender,
        "result": result,
        "sgpa": sgpa,
        "total_marks": total_marks,
        "subjects": subjects
    }


# -------------------------
# API
# -------------------------

@app.route("/parse", methods=["POST"])
def parse_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    pdf_bytes = file.read()

    full_text = ""

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += "\n" + text

    subject_headers = extract_subject_headers(full_text)
    student_blocks = extract_students_blocks(full_text)

    students = []

    for block in student_blocks:
        student = parse_student_block(block, subject_headers)
        if student:
            students.append(student)

    return jsonify({
        "status": "success",
        "students_found": len(students),
        "students": students
    })


# -------------------------
# MAIN (Railway)
# -------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
