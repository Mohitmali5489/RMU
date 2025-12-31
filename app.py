from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import re
import tempfile
import os

app = Flask(__name__)
CORS(app)

# ---------- HELPERS ----------

def clean(text):
    return re.sub(r"\s+", " ", text).strip()

def is_student_header(line):
    """
    Real student row:
    262112705 MOHIT BHARAT MALI Regular MALE MU0....
    """
    return re.search(
        r"\b\d{7}\b\s+[A-Z\s]{5,}\s+(Regular|Repeater)\s+(MALE|FEMALE)",
        line
    )

def extract_student_header(line):
    m = re.search(
        r"(?P<seat>\d{7})\s+"
        r"(?P<name>[A-Z\s]{5,})\s+"
        r"(?P<status>Regular|Repeater)\s+"
        r"(?P<gender>MALE|FEMALE)",
        line
    )
    return {
        "seat_no": m.group("seat"),
        "name": clean(m.group("name")),
        "status": m.group("status"),
        "gender": m.group("gender"),
        "result": None,
        "sgpa": None,
        "total_marks": None,
        "subjects": []
    }

def is_subject_row(line):
    """
    Subject rows always start with:
    E1 / I1 / TOT
    """
    return re.match(r"^(E\d|I\d|TOT)\b", line)

def extract_subject_marks(line, subject_codes):
    """
    Extract marks per subject in same order as subject_codes
    """
    parts = line.split()
    values = [p for p in parts if p.isdigit() or re.match(r"\d+\.\d+", p)]
    subjects = []

    for i, code in enumerate(subject_codes):
        if i < len(values):
            subjects.append({
                "subject_code": code,
                "marks": values[i]
            })
    return subjects

# ---------- ROUTE ----------

@app.route("/parse", methods=["POST"])
def parse_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400

    file = request.files["file"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        file.save(tmp.name)
        pdf_path = tmp.name

    students = []
    current_student = None
    subject_codes = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                lines = [clean(l) for l in text.split("\n") if l.strip()]

                # SUBJECT CODES LINE
                for l in lines:
                    if re.match(r"^\d{7}\s*:", l):
                        subject_codes = re.findall(r"\d{7}", l)

                for line in lines:
                    # NEW STUDENT
                    if is_student_header(line):
                        if current_student:
                            students.append(current_student)

                        current_student = extract_student_header(line)
                        continue

                    # SUBJECT MARKS
                    if current_student and is_subject_row(line):
                        marks = extract_subject_marks(line, subject_codes)
                        current_student["subjects"].extend(marks)

                    # TOTAL / RESULT
                    if current_student and "PASS" in line or "FAIL" in line:
                        if "PASS" in line:
                            current_student["result"] = "PASS"
                        elif "FAIL" in line:
                            current_student["result"] = "FAIL"

                        m = re.search(r"(\d+\.\d+)$", line)
                        if m:
                            current_student["sgpa"] = m.group(1)

        if current_student:
            students.append(current_student)

        return jsonify({
            "status": "success",
            "students_found": len(students),
            "students": students
        })

    finally:
        os.remove(pdf_path)

# ---------- MAIN ----------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
