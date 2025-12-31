from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import re
import tempfile
import os

app = Flask(__name__)
CORS(app)

@app.route("/parse", methods=["POST"])
def parse_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        file.save(tmp.name)
        pdf_path = tmp.name

    students = []
    current_student = None

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                lines = [l.strip() for l in text.split("\n") if l.strip()]

                for line in lines:

                    # -----------------------------
                    # 1️⃣ STUDENT HEADER ROW
                    # Example:
                    # 262112648 AAKANSHSA PANDURANG DHONE Regular FEMALE MU034112...
                    # -----------------------------
                    student_match = re.match(
                        r"^(\d{9})\s+([A-Z\s]+?)\s+(Regular|Repeater)\s+(MALE|FEMALE)",
                        line
                    )

                    if student_match:
                        # Save previous student
                        if current_student:
                            students.append(current_student)

                        seat_no, name, status, gender = student_match.groups()

                        current_student = {
                            "seat_no": seat_no,
                            "name": name.strip(),
                            "gender": gender,
                            "status": status,
                            "subjects": [],
                            "total_marks": None,
                            "result": None,
                            "sgpa": None
                        }
                        continue

                    # -----------------------------
                    # 2️⃣ SUBJECT ROW
                    # Example:
                    # 1162111 Financial Accounting - II 36 B+ 4
                    # -----------------------------
                    if current_student:
                        subject_match = re.match(
                            r"^(\d{6,7})\s+(.+?)\s+(\d{1,3})\s+([A-F][\+\-]?)\s+(\d+)$",
                            line
                        )

                        if subject_match:
                            code, name, marks, grade, credits = subject_match.groups()
                            current_student["subjects"].append({
                                "code": code,
                                "name": name.strip(),
                                "marks": int(marks),
                                "grade": grade,
                                "credits": int(credits)
                            })
                            continue

                    # -----------------------------
                    # 3️⃣ TOTAL / RESULT ROW
                    # Example:
                    # TOTAL 382 PASS 7.45
                    # -----------------------------
                    if current_student:
                        total_match = re.search(
                            r"TOTAL\s+(\d+)\s+(PASS|FAIL)\s+([\d\.]+)",
                            line
                        )
                        if total_match:
                            total, result, sgpa = total_match.groups()
                            current_student["total_marks"] = int(total)
                            current_student["result"] = result
                            current_student["sgpa"] = float(sgpa)
                            continue

        # Append last student
        if current_student:
            students.append(current_student)

        return jsonify({
            "status": "success",
            "students_found": len(students),
            "students": students
        })

    finally:
        os.remove(pdf_path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
