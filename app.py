from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import tempfile
import os
import re

app = Flask(__name__)
CORS(app)

def parse_office_register(pdf_path):
    students = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Extract words with their positions
            words = page.extract_words(x_tolerance=3, y_tolerance=3)
            
            # Group words into lines based on their 'top' (y-position)
            lines = {}
            for w in words:
                top = round(w['top'] / 5) * 5  # Round to nearest 5 to group slightly misaligned words
                if top not in lines:
                    lines[top] = []
                lines[top].append(w)
            
            # Sort lines by vertical position
            sorted_y = sorted(lines.keys())
            
            current_student = None
            
            for y in sorted_y:
                line_words = sorted(lines[y], key=lambda w: w['x0'])
                line_text = " ".join([w['text'] for w in line_words])
                
                # Check for Seat Number (7 digits at the start of a line)
                # The format in PDF is usually like: "262112648 AAKANSHSA..."
                seat_match = re.search(r"(\d{7,})", line_text)
                
                if seat_match:
                    # If we were processing a student, save them before starting new one
                    if current_student:
                        students.append(current_student)
                    
                    seat_no = seat_match.group(1)
                    
                    # Initialize new student
                    current_student = {
                        "seat_no": seat_no,
                        "name": "",
                        "ern": "",
                        "status": "Unknown",
                        "cgpa": "N/A",
                        "grade": "N/A",
                        "result": "N/A",
                        "raw_data": [] # Capture raw lines for debugging or deep extraction
                    }
                    
                    # Try to grab Name immediately (usually follows seat no)
                    # Text often looks like: 262112648 NAME PART 1 NAME PART 2
                    remaining_text = line_text.replace(seat_no, "").strip()
                    if remaining_text:
                        current_student["name"] = remaining_text

                # If we are inside a student block, keep processing lines
                if current_student:
                    current_student["raw_data"].append(line_text)
                    
                    # Extract ERN (Pattern: MU followed by digits)
                    ern_match = re.search(r"(MU\d{10,})", line_text)
                    if ern_match and not current_student["ern"]:
                        current_student["ern"] = ern_match.group(1)
                        
                    # Extract Name if likely split across lines (Uppercase words)
                    # This helps append the rest of the name if it was on the next line
                    # Heuristic: If line contains only uppercase words and no numbers/headers
                    if not re.search(r"\d", line_text) and "COLLEGE" not in line_text and len(line_text) > 3:
                         if len(current_student["name"].split()) < 3: # Assuming full name is usually long
                             current_student["name"] += " " + line_text

                    # Extract Result Details (usually at the bottom of the block)
                    # Look for SGPA / CGPA patterns
                    # The PDF snippet shows specific markers like "PASS", "FAILED", and GPA at end
                    if "PASS" in line_text:
                        current_student["result"] = "PASS"
                    elif "FAILED" in line_text or "FAILS" in line_text:
                        current_student["result"] = "FAILED"
                    
                    # Extract GPA (Floating point at end of data block often)
                    # Looking for pattern like "174.0 7.90909"
                    gpa_match = re.search(r"\b(\d+\.\d+)\b", line_text)
                    if gpa_match:
                        # Usually the last float found in the student block is the SGPA
                        current_student["cgpa"] = gpa_match.group(1)

            # Append the last student of the page
            if current_student:
                students.append(current_student)

    # Cleanup Names
    for s in students:
        s["name"] = clean_name(s["name"])
        del s["raw_data"] # Remove raw data before sending JSON

    return students

def clean_name(raw_name):
    # Remove common noise words found in the name column area
    noise = ["Regular", "FEMALE", "MALE", "Student", "Name", "Marks"]
    for n in noise:
        raw_name = re.sub(n, "", raw_name, flags=re.IGNORECASE)
    return raw_name.strip()

@app.route("/parse", methods=["POST"])
def parse_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    
    # Save to temp file
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    file.save(temp.name)
    temp.close()

    try:
        data = parse_office_register(temp.name)
        return jsonify({
            "status": "success",
            "students_found": len(data),
            "data": data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(temp.name):
            os.unlink(temp.name)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
