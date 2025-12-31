import re
import io
import pdfplumber
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ---------- HELPERS ----------

def clean(s):
    return re.sub(r"\s+", " ", s).strip()

def parse_subject_row(row):
    """
    Example row in PDF:
    1162111 Financial Accounting - II (THEORY)
    External 60/24  Internal 40/16  TOT 40  G A+  C 6  G*C 36
    """
    subject = {}

    # Subject code + name
    m = re.search(r"(\d{6,7})\s+(.+?)\s+\(", row)
    if not m:
        return None

    subject["code"] = m.group(1)
    subject["name"] = clean(m.group(2))

    # Marks
    ext = re.search(r"External\s+\((\d+)/(\d+)\)", row)
    inte = re.search(r"Internal\s+\((\d+)/(\d+)\)", row)
    tot = re.search(r"TOT\s+(\d+)", row)
    grade = re.search(r"G\s+([A-F][+]?|\w+)", row)
    credits = re.search(r"C\s+(\d+)", row)

    subject["external_max"] = int(ext.group(1)) if ext else None
    subject["external_marks"] = int(ext.group(2)) if ext else None
    subject["internal_max"] = int(inte.group(1)) if inte else None
    subject["internal_marks"] = int(inte.group(2)) if inte else None
    subject["total"] = int(tot.group(1)) if tot else None
    subject["grade"] = grade.group(1) if grade else None
    subject["credits"] = int(credits.group(1)) if credits else None

    return subject


# ---------- MAIN PARSER ----------

def parse_pdf(pdf_bytes):
    students = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        full_text = "\n".join(
            page.extract_text() or "" for page in pdf.pages
        )

    # Split per student (Seat No is reliable anchor)
    student_blocks = re.split(r"\n(?=\d{7}\s+[A-Z])", full_text)

    for block in student_blocks:
        seat = re.search(r"(\d{7})", block)
        name = re.search(r"\d{7}\s+([A-Z\s]+)", block)
        gender = re.search(r"\b(MALE|FEMALE)\b", block)
        result = re.search(r"\b(PASS|FAIL|ATKT)\b", block)
        sgpa = re.search(r"SGPA\s*[:\-]?\s*([\d.]+)", block)
        total = re.search(r"TOTAL\s*\(?\d+\)?\s*([\d.]+)", block)

        if not seat or not name:
            continue

        student = {
            "seat_no": seat.group(1),
            "name": clean(name.group(1)),
            "gender": gender.group(1) if gender else None,
            "result": result.group(1) if result else None,
            "sgpa": float(sgpa.group(1)) if sgpa else None,
            "total_marks": float(total.group(1)) if total else None,
            "subjects": []
        }

        # SUBJECT TABLE PARSING
        subject_rows = re.findall(
            r"\d{6,7}.*?G\s+[A-F][+]?.*?G\*C\s+\d+",
            block,
            flags=re.S
        )

        for row in subject_rows:
            sub = parse_subject_row(row)
            if sub:
                student["subjects"].append(sub)

        students.append(student)

    return students


# ---------- ROUTES ----------

@app.route("/", methods=["GET"])
def health():
    return {"status": "ok"}

@app.route("/parse", methods=["POST"])
def parse():
    if "file" not in request.files:
        return jsonify({"error": "PDF not provided"}), 400

    pdf_bytes = request.files["file"].read()
    students = parse_pdf(pdf_bytes)

    return jsonify({
        "status": "success",
        "students_found": len(students),
        "students": students
    })


# ---------- ENTRY ----------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
