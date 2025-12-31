import pdfplumber
import re
import json
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import tempfile
import os

app = Flask(__name__)
CORS(app)

def extract_office_register_data(pdf_path):
    extracted_data = {
        "university": "University of Mumbai",
        "type": "Office Register",
        "students": []
    }

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            # 1. Extract words with vertical (top) positions
            words = page.extract_words(x_tolerance=2, y_tolerance=2)
            
            # 2. Group words into lines (rows) based on 'top' position
            # We allow a small tolerance (e.g., 5 units) to group words on the same visual line
            lines = {}
            for word in words:
                y = round(word['top'] / 5) * 5
                if y not in lines:
                    lines[y] = []
                lines[y].append(word)

            # Sort lines by vertical position
            sorted_y = sorted(lines.keys())
            
            # 3. Iterate through lines to find Student Blocks
            # A student block typically starts with a Seat Number (7 digits)
            current_student = {}
            
            for y in sorted_y:
                # Sort words in this line from left to right
                line_words = sorted(lines[y], key=lambda w: w['x0'])
                line_text = " ".join([w['text'] for w in line_words])

                # PATTERN: Detect Seat Number (Start of new student)
                seat_match = re.search(r"(\d{7,})", line_text)
                
                # If we find a new seat number, save the previous student and start a new one
                if seat_match and float(line_words[0]['x0']) < 100: # Ensure it's on the left side
                    if current_student:
                        extracted_data["students"].append(current_student)
                    
                    current_student = {
                        "seat_no": seat_match.group(1),
                        "name": "",
                        "ern": "",
                        "status": "Unknown",
                        "total_marks": "N/A",
                        "sgpa": "N/A",
                        "result": "N/A"
                    }
                    
                    # Attempt to get name from the same line (text after seat no)
                    # Cleaning common noise words from name area
                    raw_name = line_text.replace(current_student['seat_no'], "").strip()
                    # Filter out purely numeric or short tokens
                    name_parts = [p for p in raw_name.split() if not p.isdigit() and len(p) > 1]
                    current_student["name"] = " ".join(name_parts)

                # Processing data INSIDE a student block
                if current_student:
                    # Capture Name continuation (if name wraps to next line)
                    # Heuristic: Line has no digits, is uppercase, and we just started the block
                    if not re.search(r"\d", line_text) and len(line_text) > 3 and "COLLEGE" not in line_text:
                         if len(current_student["name"]) < 15: # Name probably incomplete
                             current_student["name"] += " " + line_text

                    # Capture ERN
                    ern_match = re.search(r"(MU\d{10,})", line_text)
                    if ern_match:
                        current_student["ern"] = ern_match.group(1)

                    # Capture Gender/Status
                    if "FEMALE" in line_text:
                        current_student["gender"] = "FEMALE"
                    if "MALE" in line_text and "FEMALE" not in line_text:
                        current_student["gender"] = "MALE"
                    if "Regular" in line_text:
                        current_student["status"] = "Regular"

                    # Capture Total Marks
                    # Pattern: (Total) usually appears as "(374)" or similar near "PASS"
                    total_match = re.search(r"\((\d{3})\)", line_text)
                    if total_match:
                        current_student["total_marks"] = total_match.group(1)

                    # Capture Result
                    if "PASS" in line_text:
                        current_student["result"] = "PASS"
                    elif "FAILED" in line_text or "FAILS" in line_text:
                        current_student["result"] = "FAILED"
                    elif "ABSENT" in line_text:
                        current_student["result"] = "ABSENT"

                    # Capture SGPA
                    # Usually a float at the end of the block (e.g. 7.27273)
                    # We look for a float that is NOT part of course credits (usually 2.0, 4.0)
                    # SGPA is often > 0 and < 10 (or 20 in some systems, but typically < 10 here)
                    floats = re.findall(r"\b(\d+\.\d+)\b", line_text)
                    if floats:
                        # Take the last float found in the block, often the SGPA
                        for f in floats:
                            val = float(f)
                            # Basic validation for SGPA range
                            if 0.0 <= val <= 10.0: 
                                current_student["sgpa"] = f

            # Append the last student found on the page
            if current_student:
                extracted_data["students"].append(current_student)

    # Clean up Names (Remove common noise like "Mother Name" if present or stray chars)
    for s in extracted_data["students"]:
        s["name"] = s["name"].replace("Regular", "").replace("FEMALE", "").replace("MALE", "").strip()

    return extracted_data

@app.route('/parse', methods=['POST'])
def parse_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        file.save(tmp.name)
        try:
            data = extract_office_register_data(tmp.name)
            return jsonify(data)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            os.unlink(tmp.name)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
