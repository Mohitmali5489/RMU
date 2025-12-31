import re
import io
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber

app = Flask(__name__)
CORS(app)

# ---------------------------
# REGEX PATTERNS (IMPORTANT)
# ---------------------------

SEAT_NAME_PATTERN = re.compile(
    r"(?P<seat>\d{7,})\s+(?P<name>[A-Z\s]+?)\s+(Regular|ATKT|FAIL|PASS)",
    re.MULTILINE
)

GENDER_PATTERN = re.compile(r"\b(MALE|FEMALE)\b")

SUBJECT_PATTERN = re.compile(
    r"(?P<code>\d{6,})\s+"
    r"(?P<name>[A-Za-z &(),\-]+?)\s+"
    r"(?P<int>\d{1,2}|--)\s+"
    r"(?P<ext>\d{1,2}|--)\s+"
    r"(?P<total>\d{1,3})\s+"
    r"(?P<grade>[A-F][+]?|P|F)\s+"
    r"(?P<credit>\d)",
    re.MULTILINE
)

TOTAL_PATTERN = re.compile(
    r"TOTAL\s+\(?\d+\)?\s+(?P<marks>\d{2,3})"
)

SGPA_PATTERN = re.compile(r"SGPA\s+(?P<sgpa>\d+\.\d+)")

RESULT_PATTERN = re.compile(r"\b(PASS|FAIL|ATKT)\b")


# ---------------------------
# CORE PARSER
# ---------------------------

def parse_pdf(file_stream):
    full_text = ""

    with pdfplumber.open(file_stream) as pdf:
        for page in pdf.pages:
            txt = page.extract_text()
            if txt:
                full_text += "\n" + txt

    students = []
    matches = list(SEAT_NAME_PATTERN.finditer(full_text))

    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(full_text)
        block = full_text[start:end]

        seat_no = match.group("seat")
        name = match.group("name").strip()

        gender_match = GENDER_PATTERN.search(block)
        gender = gender_match.group(1) if gender_match else None

        result_match = RESULT_PATTERN.search(block)
        result = result_match.group(1) if result_match else None

        sgpa_match = SGPA_PATTERN.search(block)
        sgpa = float(sgpa_match.group("sgpa")) if sgpa_match else None

        total_match = TOTAL_PATTERN.search(block)
        total_marks = int(total_match.group("marks")) if total_match else None

        subjects = []
        for sm in SUBJECT_PATTERN.finditer(block):
            subjects.append({
                "code": sm.group("code"),
                "name": sm.group("name").strip(),
                "internal": None if sm.group("int") == "--" else int(sm.group("int")),
                "external": None if sm.group("ext") == "--" else int(sm.group("ext")),
                "total": int(sm.group("total")),
                "grade": sm.group("grade"),
                "credit": int(sm.group("credit"))
            })

        students.append({
            "seat_no": seat_no,
            "name": name,
            "gender": gender,
            "status": "Regular",
            "result": result,
            "sgpa": sgpa,
            "total_marks": total_marks,
            "subjects": subjects
        })

    return {
        "status": "success",
        "students_found": len(students),
        "students": students
    }


# ---------------------------
# API ROUTE
# ---------------------------

@app.route("/parse", methods=["POST"])
def parse_endpoint():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    data = parse_pdf(io.BytesIO(file.read()))
    return jsonify(data)


# ---------------------------
# START SERVER
# ---------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
