import pdfplumber
import re
import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def parse_office_register(pdf_path):
    students = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # 1. Extract words and cluster them into lines (rows) based on vertical position
            words = page.extract_words(x_tolerance=3, y_tolerance=3)
            lines = {}
            for w in words:
                # Group words that are roughly on the same Y-axis (within 5 units)
                y = round(w['top'] / 5) * 5
                if y not in lines:
                    lines[y] = []
                lines[y].append(w)
            
            # Sort rows from top to bottom
            sorted_y_keys = sorted(lines.keys())
            
            # 2. Process rows to find Students
            current_student = None
            
            for y in sorted_y_keys:
                # Sort words in the line from left to right
                line_words = sorted(lines[y], key=lambda w: w['x0'])
                line_text = " ".join([w['text'] for w in line_words])
                
                # --- DETECTION LOGIC ---
                
                # IGNORE Header Rows: Pattern like "(1102311)" or "OFFICE REGISTER"
                if re.match(r"^\(\d+\)", line_text) or "OFFICE REGISTER" in line_text:
                    continue

                # DETECT NEW STUDENT: Starts with 7 digits (e.g., 262112648)
                # We use strict regex `^\d{7}` to ensure it starts the line.
                seat_match = re.match(r"^(\d{7})\b", line_text)
                
                if seat_match:
                    # Save previous student if exists
                    if current_student:
                        students.append(current_student)
                    
                    seat_no = seat_match.group(1)
                    
                    # Initialize new student object
                    current_student = {
                        "seat_no": seat_no,
                        "name": "",
                        "ern": "",
                        "status": "Unknown",
                        "total_marks": "N/A",
                        "sgpa": "N/A",
                        "grade": "N/A",
                        "result": "N/A"
                    }
                    
                    # EXTRACT NAME from the same line
                    # Remove the Seat No to get the Name
                    # Text is usually: "262112648 NAME OF STUDENT"
                    raw_name_text = line_text[len(seat_no):].strip()
                    current_student["name"] = clean_name(raw_name_text)

                # --- DATA EXTRACTION (Inside a student block) ---
                if current_student:
                    # 1. ERN Detection (starts with MU)
                    ern_match = re.search(r"(MU\d{10,})", line_text)
                    if ern_match and not current_student["ern"]:
                        current_student["ern"] = ern_match.group(1)
                    
                    # 2. Name Continuation
                    # If line has NO digits and consists of Uppercase words, it might be part of the name
                    # (But ignore keywords like COLLEGE, FEMALE, etc.)
                    if (not re.search(r"\d", line_text) 
                        and len(line_text) > 2 
                        and "COLLEGE" not in line_text 
                        and "FEMALE" not in line_text 
                        and "MALE" not in line_text):
                        
                        # Only append if name looks short/incomplete
                        if len(current_student["name"]) < 20: 
                            current_student["name"] += " " + line_text.strip()

                    # 3. Status (Regular/Repeat)
                    if "Regular" in line_text:
                        current_student["status"] = "Regular"
                    
                    # 4. Result (PASS/FAIL/ABSENT)
                    if "PASS" in line_text:
                        current_student["result"] = "PASS"
                    elif "FAILED" in line_text or "FAILS" in line_text:
                        current_student["result"] = "FAILED"
                    elif "ABSENT" in line_text:
                        current_student["result"] = "ABSENT"
                        
                    # 5. SGPA / Grade Points
                    # Usually a decimal at the end of the block, e.g., "7.27"
                    # We look for a float that is reasonable for a GPA (0.00 to 10.00)
                    floats = re.findall(r"\b\d+\.\d+\b", line_text)
                    for f in floats:
                        val = float(f)
                        if 0.0 <= val <= 10.0:
                            current_student["sgpa"] = f
                            
                    # 6. Total Marks (often in brackets like (374))
                    total_match = re.search(r"\((\d{3})\)", line_text)
                    if total_match:
                        current_student["total_marks"] = total_match.group(1)

            # Append the last student found on the page
            if current_student:
                students.append(current_student)

    # Final Cleanup
    for s in students:
        s["name"] = clean_name(s["name"])

    return students

def clean_name(name_str):
    """Removes noise words from the Name field."""
    noise_words = ["FEMALE", "MALE", "Regular", "Student", "Previous", "Marks"]
    for w in noise_words:
        name_str = name_str.replace(w, "")
    
    # Remove extra spaces and non-alpha characters from ends
    return re.sub(r'\s+', ' ', name_str).strip()

@app.route("/parse", methods=["POST"])
def parse_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    
    # Save uploaded file temporarily
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    file.save(temp.name)
    temp.close()

    try:
        data = parse_office_register(temp.name)
        return jsonify({
            "status": "success",
            "count": len(data),
            "data": data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(temp.name):
            os.unlink(temp.name)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
