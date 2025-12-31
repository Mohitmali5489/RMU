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
            # 1. Cluster words into lines based on Y-position
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
                
                # --- CRITICAL FIX: LEFT MARGIN CHECK ---
                # Real Seat Numbers are always at the very start of the line (Left margin < 80)
                # Course headers often appear, but we double-check the position of the first word.
                first_word_x = float(line_words[0]['x0'])
                
                # Regex for 7-digit Seat Number
                seat_match = re.match(r"^(\d{7})\b", line_text)
                
                # 1. Check if it looks like a seat number
                # 2. Check if it's strictly on the left side (x < 80)
                # 3. Exclude known header patterns (e.g. starts with parenthesis)
                if seat_match and first_word_x < 80 and not line_text.startswith("("):
                    
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
                    
                    # Extract Name (Remove Seat No)
                    raw_name = line_text[len(seat_no):].strip()
                    current_student["name"] = clean_name(raw_name)

                # --- DATA EXTRACTION ---
                if current_student:
                    # Capture ERN
                    ern_match = re.search(r"(MU\d{10,})", line_text)
                    if ern_match and not current_student["ern"]:
                        current_student["ern"] = ern_match.group(1)
                    
                    # Capture Name Continuation (Uppercase only, no numbers, not keywords)
                    # We ensure we are NOT reading a header line by checking for digits
                    if (not re.search(r"\d", line_text) 
                        and len(line_text) > 3 
                        and "COLLEGE" not in line_text 
                        and "FEMALE" not in line_text 
                        and "MALE" not in line_text):
                        
                        # Append if name seems short
                        if len(current_student["name"].split()) < 3: 
                            current_student["name"] += " " + line_text.strip()

                    # Status
                    if "Regular" in line_text:
                        current_student["status"] = "Regular"
                    
                    # Result
                    if "PASS" in line_text:
                        current_student["result"] = "PASS"
                    elif "FAILED" in line_text or "FAILS" in line_text:
                        current_student["result"] = "FAILED"
                    elif "ABSENT" in line_text:
                        current_student["result"] = "ABSENT"
                    elif "RR" in line_text:
                        current_student["result"] = "Reserved"

                    # SGPA (Look for float between 0.0 and 10.0 at end of blocks)
                    # Exclude common credits like 2.00, 4.00, 20.00
                    floats = re.findall(r"\b(\d+\.\d+)\b", line_text)
                    for f in floats:
                        val = float(f)
                        if 0.0 < val <= 10.0 and val not in [2.0, 4.0, 20.0, 40.0, 50.0, 60.0, 100.0]:
                            current_student["sgpa"] = f

                    # Total Marks (Pattern: (374))
                    total_match = re.search(r"\((\d{3})\)", line_text)
                    if total_match:
                        current_student["total_marks"] = total_match.group(1)

            if current_student:
                students.append(current_student)

    # Final Cleanup & Deduplication
    final_data = []
    seen_seats = set()
    
    for s in students:
        s["name"] = clean_name(s["name"])
        # Deduplication check
        if s["seat_no"] not in seen_seats:
            final_data.append(s)
            seen_seats.add(s["seat_no"])

    return final_data

def clean_name(name_str):
    # Remove noise
    noise = ["FEMALE", "MALE", "Regular", "Student", "Previous", "Marks", "TOT", "Internal", "External", "College", "PRN"]
    for w in noise:
        name_str = re.sub(r'\b' + w + r'\b', '', name_str, flags=re.IGNORECASE)
    
    # Remove extra spaces
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
