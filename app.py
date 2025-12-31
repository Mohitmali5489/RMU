import re
import io
import pdfplumber
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ---------- HELPERS ----------

def extract_students_from_text(text):
    students = []

    # 🔒 Only process text AFTER student table header
    header_match = re.search(
        r"SEAT NO\s+NAME\s+STATUS\s+GENDER\s+ERN\s+COLLEGE",
        text
    )
    if not header_match:
        return students

    text = text[header_match.end():]

    # Split by real student seat numbers (7–8 digits, newline before)
    blocks = re.split(r"\n(?=\d{7,8}\s+[A-Z]{2,}\s+[A-Z]{2,})", text)

    for block in blocks:
        block = block.strip()

        # ❌ Skip subject header rows
        if ":" in block:
            continue

        # --- Seat No + Full Name ---
        m = re.match(r"^(\d{7,8})\s+([A-Z]{2,}(?:\s+[A-Z]{2,})+)", block)
        if not m:
            continue

        seat_no = m.group(1)
        name = m.group(2).strip()

        # --- Gender ---
        gender = None
        if re.search(r"\bMALE\b", block):
            gender = "MALE"
        elif re.search(r"\bFEMALE\b", block):
            gender = "FEMALE"

        # --- Status ---
        status = "Regular" if " Regular " in block else None

        # --- Result ---
        result = None
        if re.search(r"\bPASS\b", block):
            result = "PASS"
        elif re.search(r"\bFAIL\b", block):
            result = "FAIL"

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
            college = col.group(1).strip()

        # --- Subjects ---
        subjects = []
        subject_pattern = re.compile(
            r"(\d{6,7})\s+([A-Za-z &()-]+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([A+BCDEF]+)\s+(\d+)"
        )

        for sm in subject_pattern.finditer(block):
            subjects.append({
                "code": sm.group(1),
                "name": sm.group(2).strip(),
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
