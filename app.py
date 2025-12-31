import re
import io
import pdfplumber
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ---------- HELPERS ----------

def clean(text):
    return re.sub(r"\s+", " ", text).strip()


def extract_students_from_text(text):
    students = []

    # Each student starts with seat number (7–8 digits)
    blocks = re.split(r"\n(?=\d{7,8}\s+[A-Z])", text)

    for block in blocks:
        block = block.strip()
        if not re.match(r"^\d{7,8}", block):
            continue

        lines = block.split("\n")

        # --- Seat No & Name ---
        m = re.match(r"^(\d{7,8})\s+([A-Z ]+)", lines[0])
        if not m:
            continue

        seat_no = m.group(1)
        name = clean(m.group(2))

        # --- Gender ---
        gender = "MALE" if " MALE " in block else "FEMALE" if " FEMALE " in block else None

        # --- Status ---
        status = "Regular" if " Regular " in block else None

        # --- Result ---
        result = "PASS" if " PASS " in block else "FAIL" if " FAIL " in block else None

        # --- Total Marks ---
        total_marks = None
        tm = re.search(r"MARKS\s*\(?(\d+)\)?", block)
        if tm:
            total_marks = int(tm.group(1))

        # --- SGPA ---
        sgpa = None
        sg = re.search(r"SGPA[:\s]+([\d.]+)", block)
        if sg:
            sgpa = float(sg.group(1))

        # --- College ---
        college = None
        col = re.search(r"MU-\d+:(.+)", block)
        if col:
            college = clean(col.group(1))

        # --- Subjects ---
        subjects = []
        subject_pattern = re.compile(
            r"(\d{6,7})\s+([A-Za-z &()-]+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([A+BCDEF]+)\s+(\d+)",
            re.MULTILINE
        )

        for sm in subject_pattern.finditer(block):
            subjects.append({
                "code": sm.group(1),
                "name": clean(sm.group(2)),
                "internal": int(sm.group(3)),
                "external": int(sm.group(4)),
                "total": int(sm.group(5)),
                "grade": sm.group(6),
                "credits": int(sm.group(7))
            })

        students.append({
            "seat_no": seat_no,
            "name": name,
            "gender": gender,
            "status": status,
            "college": college,
            "result": result,
            "total_marks": total_marks,
            "sgpa": sgpa,
            "subjects": subjects
        })

    return students


# ---------- ROUTES ----------

@app.route("/parse", methods=["POST"])
def parse_pdf():
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400

    file = request.files["file"]

    text = ""
    with pdfplumber.open(io.BytesIO(file.read())) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    students = extract_students_from_text(text)

    return jsonify({
        "status": "success",
        "students": students,
        "students_found": len(students)
    })


@app.route("/")
def health():
    return "RMU PDF Parser is running"
