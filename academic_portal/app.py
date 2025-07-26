from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import os
from utils import (
    is_valid_id,
    is_strong_password,
    hash_password,
    check_password_match,
    load_json,
    save_json,
    get_user_by_id
)
import uuid
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DATA_FILE = os.path.join(BASE_DIR, "data", "users.json")
ASS_FILE = os.path.join(BASE_DIR, "data", "assignments.json")
SUB_FILE = os.path.join(BASE_DIR, "data", "submissions.json")
GRADE_FILE = os.path.join(BASE_DIR, "data", "grades.json")
MSG_FILE = os.path.join(BASE_DIR, "data", "messages.json")  # New messages file

app = Flask(__name__)
app.secret_key = 'your-secret-key'  # Use env var in production

# ---------- HELPER FUNCTIONS ----------

def get_grade_letter(score):
    """Convert numerical grade to letter grade"""
    if not isinstance(score, (int, float)):
        return 'N/A'
    if score >= 90: return 'A'
    if score >= 80: return 'B'
    if score >= 70: return 'C'
    if score >= 60: return 'D'
    return 'F'

def calculate_average(grades):
    """Calculate average grade from a list of grade dictionaries"""
    if not grades:
        return 0
    valid_grades = [g['grade'] for g in grades if isinstance(g.get('grade'), (int, float))]
    if not valid_grades:
        return 0
    return round(sum(valid_grades) / len(valid_grades), 2)

def get_user_messages(user_id):
    """Get all messages for a user (both sent and received)"""
    messages = load_json(MSG_FILE) or []
    return [msg for msg in messages if msg['sender_id'] == user_id or msg['receiver_id'] == user_id]

def user_exists(user_id):
    """Check if a user exists in the system"""
    users = load_json(USER_DATA_FILE) or []
    return any(user['id'] == user_id for user in users)

# ---------- HOME ----------

@app.route("/")
def home():
    return redirect(url_for("login"))

# ---------- REGISTER ----------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user_id = request.form.get("id")
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        # Validate ID
        valid_id, role = is_valid_id(user_id)
        if not valid_id:
            flash("Invalid ID format.")
            return redirect(url_for("register"))

        # Validate password
        if not is_strong_password(password):
            flash("Password must be at least 8 characters and include uppercase, lowercase, digit, and special char.")
            return redirect(url_for("register"))

        # Check if user already exists
        if get_user_by_id(user_id, USER_DATA_FILE):
            flash("User ID already registered.")
            return redirect(url_for("register"))

        # Hash password and save
        hashed = hash_password(password)
        user_data = {
            "id": user_id,
            "name": name,
            "email": email,
            "password": hashed,
            "role": role,
            "theme": "dark" if role == "faculty" else "colorful"
        }

        users = load_json(USER_DATA_FILE)
        users.append(user_data)
        save_json(USER_DATA_FILE, users)

        flash("Registration successful. Please login.")
        return redirect(url_for("login"))

    return render_template("register.html")

# ---------- LOGIN ----------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_id = request.form.get("id")
        password = request.form.get("password")

        user = get_user_by_id(user_id, USER_DATA_FILE)
        if user and check_password_match(password, user["password"]):
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["theme"] = user.get("theme", "dark")
            flash("Login successful.")
            return redirect(url_for("dashboard"))

        flash("Invalid ID or password.")
        return redirect(url_for("login"))

    return render_template("login.html")

# ---------- LOGOUT ----------

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for("login"))

# ---------- DASHBOARD ----------

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        flash("Please login first.")
        return redirect(url_for("login"))

    role = session.get("role")
    if role == "faculty":
        return redirect(url_for("faculty_dashboard"))
    elif role == "student":
        return redirect(url_for("student_dashboard"))
    else:
        flash("Unknown role.")
        return redirect(url_for("login"))

# ---------- MESSAGING SYSTEM ----------

@app.route("/inbox")
def inbox():
    if "user_id" not in session:
        flash("Please login first.")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    messages = get_user_messages(user_id)
    
    # Get user details for display
    users = load_json(USER_DATA_FILE) or []
    user_map = {user['id']: user['name'] for user in users}
    
    return render_template("inbox.html",
                         messages=messages,
                         user_map=user_map,
                         theme=session.get("theme", "dark"))

@app.route("/send_message", methods=["POST"])
def send_message():
    if "user_id" not in session:
        flash("Please login first.")
        return redirect(url_for("login"))

    sender_id = session["user_id"]
    receiver_id = request.form.get("receiver_id")
    content = request.form.get("content")

    # Validate receiver exists
    if not user_exists(receiver_id):
        flash("Recipient does not exist.", "error")
        return redirect(request.referrer or url_for("inbox"))

    # Create message
    message = {
        "message_id": str(uuid.uuid4()),
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "is_read": False,
        "deleted_by_sender": False,
        "deleted_by_receiver": False
    }

    # Save message
    messages = load_json(MSG_FILE) or []
    messages.append(message)
    save_json(MSG_FILE, messages)

    flash("Message sent successfully!", "success")
    return redirect(url_for("inbox"))

@app.route("/delete_message/<message_id>", methods=["POST"])
def delete_message(message_id):
    if "user_id" not in session:
        flash("Please login first.")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    messages = load_json(MSG_FILE) or []
    
    for message in messages:
        if message['message_id'] == message_id:
            # Mark as deleted by the appropriate user
            if message['sender_id'] == user_id:
                message['deleted_by_sender'] = True
            elif message['receiver_id'] == user_id:
                message['deleted_by_receiver'] = True
            
            # If both sides have deleted, remove the message completely
            if message['deleted_by_sender'] and message['deleted_by_receiver']:
                messages.remove(message)
            
            save_json(MSG_FILE, messages)
            flash("Message deleted successfully.", "success")
            return redirect(url_for("inbox"))

    flash("Message not found.", "error")
    return redirect(url_for("inbox"))

@app.route("/mark_as_read/<message_id>", methods=["POST"])
def mark_as_read(message_id):
    if "user_id" not in session:
        return {"status": "error", "message": "Not logged in"}, 401

    user_id = session["user_id"]
    messages = load_json(MSG_FILE) or []
    
    for message in messages:
        if (message['message_id'] == message_id and 
            message['receiver_id'] == user_id and
            not message['is_read']):
            message['is_read'] = True
            save_json(MSG_FILE, messages)
            return {"status": "success"}
    
    return {"status": "error", "message": "Message not found"}, 404

# ---------- STUDENT DASHBOARD ----------

@app.route("/student_dashboard")
def student_dashboard():
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("login"))

    try:
        student_id = session["user_id"]
        
        # Load all data files with error handling
        try:
            assignments = load_json(ASS_FILE) or []
            submissions = load_json(SUB_FILE) or []
            grades = load_json(GRADE_FILE) or []
            messages = get_user_messages(student_id)
        except Exception as e:
            app.logger.error(f"Error loading data files: {str(e)}")
            assignments, submissions, grades, messages = [], [], [], []

        # Filter available assignments (not submitted yet)
        student_submissions = [s for s in submissions if s.get("student_id") == student_id]
        submitted_ids = [s["assignment_id"] for s in student_submissions if "assignment_id" in s]
        available_assignments = [a for a in assignments if a.get("assignment_id") not in submitted_ids]
        
        # Get student grades with assignment details
        student_grades = []
        for grade in grades:
            if grade.get("student_id") == student_id:
                assignment = next((a for a in assignments if a.get("assignment_id") == grade.get("assignment_id")), None)
                if assignment:
                    grade_data = {
                        "assignment_title": assignment.get("title", "Untitled Assignment"),
                        "course_id": assignment.get("course_id", "N/A"),
                        "grade": grade.get("grade"),
                        "graded_date": grade.get("graded_date", ""),
                        "feedback": grade.get("feedback", ""),
                        "submission_date": next(
                            (s.get("submission_date", "") for s in submissions 
                             if s.get("assignment_id") == grade.get("assignment_id") 
                             and s.get("student_id") == student_id),
                            ""
                        ),
                        "file_path": next(
                            (s.get("file_path", "") for s in submissions 
                             if s.get("assignment_id") == grade.get("assignment_id") 
                             and s.get("student_id") == student_id),
                            ""
                        )
                    }
                    student_grades.append(grade_data)

        # Sort grades by graded date (newest first)
        student_grades = sorted(student_grades, 
                              key=lambda x: x.get("graded_date", ""), 
                              reverse=True)
        
        # Calculate average grade
        avg_grade = calculate_average(student_grades)

        # Get unread message count
        unread_count = sum(1 for msg in messages if msg['receiver_id'] == student_id and not msg['is_read'])

        return render_template("student_dashboard.html",
                            user_id=student_id,
                            theme=session.get("theme", "dark"),
                            assignments=available_assignments,
                            grades=student_grades,
                            avg_grade=avg_grade,
                            unread_count=unread_count,
                            get_grade_letter=get_grade_letter)
    except Exception as e:
        app.logger.error(f"Error in student dashboard: {str(e)}")
        flash("Error loading dashboard data", "error")
        return render_template("student_dashboard.html",
                            user_id=session["user_id"],
                            theme=session.get("theme", "dark"),
                            assignments=[],
                            grades=[],
                            avg_grade=0,
                            unread_count=0)

# ---------- FACULTY DASHBOARD ----------

@app.route("/teacher_dashboard")
def faculty_dashboard():
    if session.get("role") != "faculty":
        return redirect(url_for("login"))

    try:
        assignments = load_json(ASS_FILE) or []
        user_id = session.get("user_id")
        user_assignments = [a for a in assignments if a.get("created_by") == user_id]
        submissions = load_json(SUB_FILE) or []
        messages = get_user_messages(user_id)
        
        # Get unread message count
        unread_count = sum(1 for msg in messages if msg['receiver_id'] == user_id and not msg['is_read'])

        return render_template(
            "teacher_dashboard.html",
            assignments=user_assignments,
            submissions=submissions,
            theme=session.get("theme", "dark"),
            unread_count=unread_count
        )
    except Exception as e:
        app.logger.error(f"Error in faculty dashboard: {str(e)}")
        flash("Error loading dashboard data", "error")
        return render_template(
            "teacher_dashboard.html",
            assignments=[],
            submissions=[],
            theme=session.get("theme", "dark"),
            unread_count=0
        )

# ---------- ASSIGNMENT SUBMISSION ----------

@app.route("/submit_assignment", methods=["POST"])
def submit_assignment():
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("login"))

    try:
        assignment_id = request.form.get("assignment_id")
        text_response = request.form.get("text_response")
        student_id = session["user_id"]
        
        # Handle file upload
        file_path = ""
        file = request.files.get("submission_file")
        if file and file.filename:
            os.makedirs("student_submissions", exist_ok=True)
            filename = f"{assignment_id}_{student_id}_{file.filename}"
            file_path = os.path.join("student_submissions", filename)
            file.save(file_path)

        # Load assignment details
        assignments = load_json(ASS_FILE) or []
        assignment = next((a for a in assignments if a.get("assignment_id") == assignment_id), None)
        
        if not assignment:
            flash("Assignment not found", "error")
            return redirect(url_for("student_dashboard"))

        # Create submission record
        submission = {
            "submission_id": str(uuid.uuid4()),
            "assignment_id": assignment_id,
            "student_id": student_id,
            "assignment_title": assignment.get("title", "Untitled Assignment"),
            "course_id": assignment.get("course_id", "N/A"),
            "text_response": text_response,
            "file_path": file_path,
            "submission_date": datetime.now().isoformat(),
            "status": "submitted",
            "grade": None,
            "feedback": None
        }

        # Save submission
        submissions = load_json(SUB_FILE) or []
        submissions.append(submission)
        save_json(SUB_FILE, submissions)

        flash("Assignment submitted successfully!", "success")
    except Exception as e:
        app.logger.error(f"Error submitting assignment: {str(e)}")
        flash("Error submitting assignment", "error")

    return redirect(url_for("student_dashboard"))

@app.route("/download_submission/<filename>")
def download_submission(filename):
    if "user_id" not in session or session.get("role") != "faculty":
        flash("Unauthorized access", "error")
        return redirect(url_for("login"))

    try:
        safe_filename = os.path.basename(filename)
        submissions_dir = os.path.join(app.root_path, "student_submissions")
        
        if not os.path.exists(submissions_dir):
            os.makedirs(submissions_dir, exist_ok=True)
            flash("Submissions directory not found - created new one", "warning")
            return redirect(url_for("faculty_dashboard"))

        file_path = os.path.join(submissions_dir, safe_filename)
        if not os.path.exists(file_path):
            flash("Requested file not found", "error")
            return redirect(url_for("faculty_dashboard"))

        if not os.path.realpath(file_path).startswith(os.path.realpath(submissions_dir)):
            flash("Invalid file path", "error")
            return redirect(url_for("faculty_dashboard"))

        submissions = load_json(SUB_FILE) or []
        submission = next(
            (s for s in submissions if s.get("file_path", "").endswith(safe_filename)),
            None
        )
        
        download_name = None
        if submission:
            original_filename = safe_filename.split("_")[-1]
            download_name = f"{submission['student_id']}_{submission['assignment_id']}_{original_filename}"

        return send_from_directory(
            submissions_dir,
            safe_filename,
            as_attachment=True,
            download_name=download_name
        )

    except Exception as e:
        app.logger.error(f"Error downloading file {filename}: {str(e)}")
        flash("Error downloading file", "error")
        return redirect(url_for("faculty_dashboard"))

# ---------- ASSIGNMENT MANAGEMENT ----------

@app.route("/create_assignment", methods=["POST"])
def create_assignment():
    if "user_id" not in session or session["role"] != "faculty":
        return redirect("/login")

    try:
        data = request.form
        title = data.get("title")
        description = data.get("description")
        due_date = data.get("due_date")
        course_id = data.get("course_id")
        faculty_id = session["user_id"]
        assignment_id = str(uuid.uuid4())

        attachment_path = ""
        file = request.files.get("attachment")
        if file and file.filename:
            os.makedirs("attachments", exist_ok=True)
            ext = os.path.splitext(file.filename)[1]
            filename = f"{assignment_id}_desc{ext}"
            attachment_path = os.path.join("attachments", filename)
            file.save(attachment_path)

        new_assignment = {
            "assignment_id": assignment_id,
            "title": title,
            "description": description,
            "due_date": due_date,
            "course_id": course_id,
            "attachment": attachment_path,
            "created_by": faculty_id
        }
        
        assignments = load_json(ASS_FILE) or []
        assignments.append(new_assignment)
        save_json(ASS_FILE, assignments)

        flash("Assignment created successfully", "success")
    except Exception as e:
        app.logger.error(f"Error creating assignment: {str(e)}")
        flash("Error creating assignment", "error")

    return redirect("/teacher_dashboard")

@app.route("/delete_assignment/<assignment_id>", methods=["POST"])
def delete_assignment(assignment_id):
    if session.get("role") != "faculty":
        return redirect(url_for("login"))
    
    try:
        assignments = load_json(ASS_FILE) or []
        updated_assignments = [a for a in assignments if a.get("assignment_id") != assignment_id]
        save_json(ASS_FILE, updated_assignments)
        flash("Assignment deleted successfully", "success")
    except Exception as e:
        app.logger.error(f"Error deleting assignment: {str(e)}")
        flash(f"Error deleting assignment: {str(e)}", "error")
    
    return redirect(url_for("faculty_dashboard"))

@app.route("/grade_submission", methods=["POST"])
def grade_submission():
    if session.get("role") != "faculty":
        return redirect(url_for("login"))

    try:
        submission_id = request.form.get("submission_id")
        student_id = request.form.get("student_id")
        assignment_id = request.form.get("assignment_id")
        grade = int(request.form.get("grade"))
        feedback = request.form.get("feedback", "")

        submissions = load_json(SUB_FILE) or []
        grades = load_json(GRADE_FILE) or []

        submission = next((s for s in submissions if s.get("submission_id") == submission_id), None)
        if not submission:
            flash("Submission not found", "error")
            return redirect(url_for("faculty_dashboard"))

        submission["status"] = "graded"
        submission["grade"] = grade
        submission["feedback"] = feedback
        save_json(SUB_FILE, submissions)

        grade_record = {
            "grade_id": str(uuid.uuid4()),
            "student_id": student_id,
            "assignment_id": assignment_id,
            "submission_id": submission_id,
            "grade": grade,
            "feedback": feedback,
            "graded_date": datetime.now().isoformat(),
            "graded_by": session["user_id"]
        }
        
        # Remove any existing grade for this submission
        grades = [g for g in grades if not (
            g.get("student_id") == student_id and 
            g.get("assignment_id") == assignment_id
        )]
        
        grades.append(grade_record)
        save_json(GRADE_FILE, grades)

        flash("Grade submitted successfully!", "success")
    except Exception as e:
        app.logger.error(f"Error submitting grade: {str(e)}")
        flash(f"Error submitting grade: {str(e)}", "error")

    return redirect(url_for("faculty_dashboard"))

# ---------- THEME MANAGEMENT ----------

@app.context_processor
def inject_request():
    return dict(request=request)

@app.route("/toggle_theme", methods=["POST"])
def toggle_theme():
    current = session.get("theme", "dark")
    session["theme"] = "colorful" if current == "dark" else "dark"
    return redirect(request.referrer or url_for("dashboard"))

# ---------- RUN SERVER ----------

if __name__ == "__main__":
    # Create data directory if it doesn't exist
    os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
    
    # Initialize messages file if it doesn't exist
    if not os.path.exists(MSG_FILE):
        save_json(MSG_FILE, [])
    
    app.run(debug=True)