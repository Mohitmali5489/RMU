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
                y = round(w['top'] / 5) * 5
                if y not in lines:
                    lines[y] = []
                lines[y].append(w)
            
            sorted_y_keys = sorted(lines.keys())
            
            current_student = None
            
            for y in sorted_y_keys:
                line_words = sorted(lines[y], key=lambda w: w['x0'])
                line_text = " ".join([w['text'] for w in line_words])
                
                # --- FILTERING LOGIC ---
                # Ignore lines that look like Course Headers even if they start with 7 digits.
                # Common words in course titles found in your PDF:
                course_keywords = ["Social Media", "Financial Accounting", "Auditing", 
                                   "Vocational Skills", "Introduction to", "Environmental", 
                                   "Foundation of", "Lekhan kaushalya"]
                
                is_course_header = any(k in line_text for k in course_keywords)

                # --- STUDENT DETECTION ---
                # Match 7-digit Seat Number at the start of the line
                seat_match = re.match(r"^(\d{7})\b", line_text)
                
                # Only treat as a student if it's NOT a course header
                if seat_match and not is_course_header:
                    if current_student:
                        students.append(current_student)
                    
                    seat_no = seat_match.group(1)
                    
                    current_student = {
                        "seat_no": seat_no,
                        "name": "",
                        "ern": "",
                        "status": "Unknown",
                        "total_marks": "N/A",
                        "sgpa": "N/A",
                        "result": "N/A"
                    }
                    
                    # Extract Name (Everything after seat number)
                    raw_name_text = line_text[len(seat_no):].strip()
                    current_student["name"] = clean_name(raw_name_text)

                # --- DATA EXTRACTION (Inside a student block) ---
                if current_student:
                    # Capture ERN (starts with MU)
                    ern_match = re.search(r"(MU\d{10,})", line_text)
                    if ern_match and not current_student["ern"]:
                        current_student["ern"] = ern_match.group(1)
                    
                    # Capture Name Continuation (Uppercase words, no digits, no keywords)
                    if (not re.search(r"\d", line_text) 
                        and len(line_text) > 3 
                        and "COLLEGE" not in line_text 
                        and "FEMALE" not in line_text 
                        and "MALE" not in line_text
                        and not is_course_header): # crucial check
                        
                        # Heuristic: Append if name seems short or doesn't have 3 parts yet
                        if len(current_student["name"].split()) < 3: 
                            current_student["name"] += " " + line_text.strip()

                    # Capture Status
                    if "Regular" in line_text:
                        current_student["status"] = "Regular"
                    
                    # Capture Result
                    if "PASS" in line_text:
                        current_student["result"] = "PASS"
                    elif "FAILED" in line_text or "FAILS" in line_text:
                        current_student["result"] = "FAILED"
                    elif "ABSENT" in line_text:
                        current_student["result"] = "ABSENT"
                    elif "RR" in line_text: # Reserved Result
                        current_student["result"] = "RR"

                    # Capture SGPA
                    # Usually the last distinct float in the block
                    # Filter out 2.00, 4.00 which are credits
                    floats = re.findall(r"\b(\d+\.\d+)\b", line_text)
                    for f in floats:
                        val = float(f)
                        if 0.0 < val <= 10.0 and val not in [2.0, 4.0, 20.0, 40.0, 50.0]:
                            current_student["sgpa"] = f

                    # Capture Total Marks
                    # Pattern: (374) or similar
                    total_match = re.search(r"\((\d{3})\)", line_text)
                    if total_match:
                        current_student["total_marks"] = total_match.group(1)

            if current_student:
                students.append(current_student)

    # Final Cleanup
    for s in students:
        s["name"] = clean_name(s["name"])

    return students

def clean_name(name_str):
    # Remove junk words that appear near the name column
    noise = ["FEMALE", "MALE", "Regular", "Student", "Previous", "Marks", "TOT", "Internal", "External", "College"]
    for w in noise:
        name_str = re.sub(r'\b' + w + r'\b', '', name_str, flags=re.IGNORECASE)
    
    # Remove extra spaces or non-alpha chars from edges
    name_str = re.sub(r'\s+', ' ', name_str).strip()
    return name_str

@app.route("/parse", methods=["POST"])
def parse_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
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
