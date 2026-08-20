from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_file
)

import sqlite3
import uuid
import os
import re
import qrcode
import pytesseract

from PIL import Image, ImageEnhance, ImageFilter
from werkzeug.utils import secure_filename
from datetime import datetime
from io import BytesIO


# =========================================================
# APP CONFIG
# =========================================================

app = Flask(__name__)

app.secret_key = "AI_DIGITAL_CREDENTIAL_SECRET_2026"

BASE_DIR = app.root_path

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "uploads"
)

QR_FOLDER = os.path.join(
    BASE_DIR,
    "static",
    "qr_codes"
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(QR_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# =========================================================
# TESSERACT CONFIG
# =========================================================

TESSERACT_PATH = os.environ.get(
    "TESSERACT_CMD",
    "tesseract"
)

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


# =========================================================
# ALLOWED FILE TYPES
# =========================================================

ALLOWED_EXTENSIONS = {
    "pdf",
    "png",
    "jpg",
    "jpeg"
}


def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db():

    conn = sqlite3.connect(
        os.path.join(
            BASE_DIR,
            "database.db"
        )
    )

    conn.row_factory = sqlite3.Row

    return conn


# =========================================================
# DATABASE CREATION
# =========================================================

def create_database():

    conn = get_db()

    # =====================================================
    # USERS
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            email TEXT UNIQUE NOT NULL,

            password TEXT NOT NULL,

            credential_id TEXT UNIQUE NOT NULL,

            certificate_type TEXT NOT NULL,

            certificate_title TEXT NOT NULL,

            organization TEXT NOT NULL,

            issue_date TEXT NOT NULL

        )
    """)

    # =====================================================
    # CERTIFICATE FILE
    # =====================================================

    try:

        conn.execute("""
            ALTER TABLE users
            ADD COLUMN certificate_file TEXT
        """)

    except sqlite3.OperationalError:

        pass

    # =====================================================
    # VALIDATION CODE
    # =====================================================

    try:

        conn.execute("""
            ALTER TABLE users
            ADD COLUMN validation_code TEXT
        """)

    except sqlite3.OperationalError:

        pass

    # =====================================================
    # CERTIFICATE UPLOADS
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS certificate_uploads (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            credential_id TEXT NOT NULL,

            filename TEXT NOT NULL,

            file_path TEXT NOT NULL,

            uploaded_at TEXT NOT NULL

        )
    """)

    # =====================================================
    # VERIFICATION HISTORY
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS verification_history (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            credential_id TEXT NOT NULL,

            status TEXT NOT NULL,

            verification_method TEXT NOT NULL,

            verified_at TEXT NOT NULL

        )
    """)

    # =====================================================
    # ADMINS
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS admins (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            username TEXT UNIQUE NOT NULL,

            password TEXT NOT NULL

        )
    """)

    # =====================================================
    # DEFAULT ADMIN
    # =====================================================

    admin = conn.execute(
        """
        SELECT *
        FROM admins
        WHERE username = ?
        """,
        ("admin",)
    ).fetchone()

    if admin is None:

        conn.execute(
            """
            INSERT INTO admins
            (
                username,
                password
            )
            VALUES (?, ?)
            """,
            (
                "admin",
                "admin123"
            )
        )

    conn.commit()

    conn.close()


def generate_qr(credential_id):

    verification_url = (
        f"https://ai-credential-verification.onrender.com/verify/{credential_id}"
    )

    qr = qrcode.make(verification_url)

    qr_path = os.path.join(
        QR_FOLDER,
        f"{credential_id}.png"
    )

    qr.save(qr_path)

    return qr_path
# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# REGISTER
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        name = request.form.get("name")

        email = request.form.get("email")

        password = request.form.get("password")

        certificate_type = request.form.get(
            "certificate_type",
            "Online Course"
        )

        certificate_title = request.form.get(
            "certificate_title",
            "Web Application"
        )

        organization = request.form.get(
            "organization",
            "ABC Institute"
        )

        issue_date = request.form.get("issue_date")

        if not issue_date:

            issue_date = datetime.now().strftime(
                "%Y-%m-%d"
            )

        credential_id = (
            "CRED-2026-"
            +
            uuid.uuid4().hex[:8].upper()
        )

        conn = get_db()

        try:

            conn.execute(
                """
                INSERT INTO users
                (
                    name,
                    email,
                    password,
                    credential_id,
                    certificate_type,
                    certificate_title,
                    organization,
                    issue_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    email,
                    password,
                    credential_id,
                    certificate_type,
                    certificate_title,
                    organization,
                    issue_date
                )
            )

            conn.commit()

            conn.close()

            return redirect(
                url_for("home")
            )

        except sqlite3.IntegrityError:

            conn.close()

            return """
            <h2>Email already registered</h2>
            <a href="/register">Go Back</a>
            """

    return render_template(
        "register.html"
    )


# =========================================================
# STUDENT LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["POST"]
)
def login():

    email = request.form.get("email")

    password = request.form.get("password")

    conn = get_db()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE email = ?
        AND password = ?
        """,
        (
            email,
            password
        )
    ).fetchone()

    conn.close()

    if user:

        session["student_id"] = user["id"]

        session["student_name"] = user["name"]

        session["student_email"] = user["email"]

        return redirect(
            url_for("dashboard")
        )

    return """
    <h2>Invalid Email or Password</h2>
    <a href="/">Back</a>
    """


# =========================================================
# STUDENT DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "student_id" not in session:

        return redirect(
            url_for("home")
        )

    conn = get_db()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (
            session["student_id"],
        )
    ).fetchone()

    if not user:

        conn.close()

        return redirect(
            url_for("home")
        )

    history = conn.execute(
        """
        SELECT *
        FROM verification_history
        WHERE credential_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (
            user["credential_id"],
        )
    ).fetchone()

    upload_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM certificate_uploads
        WHERE credential_id = ?
        """,
        (
            user["credential_id"],
        )
    ).fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",

        user=dict(user),

        history=dict(history)
        if history
        else None,

        upload_count=upload_count
    )


# =========================================================
# STUDENT CERTIFICATE
# =========================================================

@app.route("/certificate")
def certificate():

    if "student_id" not in session:

        return redirect(
            url_for("home")
        )

    conn = get_db()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (
            session["student_id"],
        )
    ).fetchone()

    conn.close()

    if not user:

        return redirect(
            url_for("home")
        )

    qr_path = generate_qr(
        user["credential_id"]
    )

    return render_template(
        "certificate.html",

        user=dict(user),

        qr_code=f"{user['credential_id']}.png",

        qr_path=qr_path
    )


# =========================================================
# DOWNLOAD GENERATED CERTIFICATE
# =========================================================

@app.route(
    "/download-certificate"
)
def download_certificate():

    if "student_id" not in session:

        return redirect(
            url_for("home")
        )

    conn = get_db()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (
            session["student_id"],
        )
    ).fetchone()

    conn.close()

    if not user:

        return redirect(
            url_for("home")
        )

    try:

        from reportlab.pdfgen import canvas

        from reportlab.lib.pagesizes import A4

        from reportlab.lib.units import mm

    except ImportError:

        return """
        <h2>ReportLab is missing.</h2>
        <p>Run: pip install reportlab</p>
        """

    pdf = BytesIO()

    document = canvas.Canvas(
        pdf,
        pagesize=A4
    )

    width, height = A4

    document.setFont(
        "Helvetica-Bold",
        24
    )

    document.drawCentredString(
        width / 2,
        height - 45 * mm,
        "AI DIGITAL CREDENTIAL"
    )

    document.setFont(
        "Helvetica-Bold",
        20
    )

    document.drawCentredString(
        width / 2,
        height - 60 * mm,
        "CERTIFICATE"
    )

    document.setFont(
        "Helvetica",
        12
    )

    document.drawCentredString(
        width / 2,
        height - 82 * mm,
        "This certificate is proudly presented to"
    )

    document.setFont(
        "Helvetica-Bold",
        22
    )

    document.drawCentredString(
        width / 2,
        height - 98 * mm,
        user["name"]
    )

    y = height - 125 * mm

    details = [

        (
            "Certificate Type",
            user["certificate_type"]
        ),

        (
            "Certificate Title",
            user["certificate_title"]
        ),

        (
            "Issuing Organization",
            user["organization"]
        ),

        (
            "Issue Date",
            user["issue_date"]
        ),

        (
            "Credential ID",
            user["credential_id"]
        )

    ]

    for label, value in details:

        document.setFont(
            "Helvetica-Bold",
            11
        )

        document.drawString(
            40 * mm,
            y,
            label + ":"
        )

        document.setFont(
            "Helvetica",
            11
        )

        document.drawString(
            90 * mm,
            y,
            str(value)
        )

        y -= 13 * mm

    qr_path = generate_qr(
        user["credential_id"]
    )

    if os.path.exists(qr_path):

        document.drawImage(
            qr_path,
            width - 65 * mm,
            35 * mm,
            width=40 * mm,
            height=40 * mm
        )

    document.setFont(
        "Helvetica-Bold",
        14
    )

    document.drawCentredString(
        width / 2,
        45 * mm,
        "AUTHENTIC DIGITAL CREDENTIAL"
    )

    document.setFont(
        "Helvetica",
        9
    )

    document.drawCentredString(
        width / 2,
        30 * mm,
        "AI Digital Credential Verification System"
    )

    document.save()

    pdf.seek(0)

    return send_file(
        pdf,
        as_attachment=True,
        download_name=(
            user["credential_id"]
            +
            ".pdf"
        ),
        mimetype="application/pdf"
    )


# =========================================================
# DOWNLOAD ORIGINAL CERTIFICATE
# ADMIN ONLY
# =========================================================

@app.route(
    "/download-original/<credential_id>"
)
def download_original(credential_id):

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    upload = conn.execute(
        """
        SELECT *
        FROM certificate_uploads
        WHERE credential_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (
            credential_id,
        )
    ).fetchone()

    conn.close()

    if not upload:

        return "Original certificate has not been uploaded.", 404

    file_path = upload["file_path"]

    if not os.path.isabs(file_path):

        file_path = os.path.join(
            BASE_DIR,
            file_path
        )

    if not os.path.exists(file_path):

        return "Original certificate file not found.", 404

    return send_file(
        file_path,
        as_attachment=True,
        download_name=upload["filename"]
    )


# =========================================================
# VIEW ORIGINAL CERTIFICATE
# ADMIN ONLY
# =========================================================

@app.route(
    "/view-original/<credential_id>"
)
def view_original(credential_id):

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    upload = conn.execute(
        """
        SELECT *
        FROM certificate_uploads
        WHERE credential_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (
            credential_id,
        )
    ).fetchone()

    conn.close()

    if not upload:

        return "Original certificate has not been uploaded.", 404

    file_path = upload["file_path"]

    if not os.path.isabs(file_path):

        file_path = os.path.join(
            BASE_DIR,
            file_path
        )

    if not os.path.exists(file_path):

        return "Original certificate file not found.", 404

    return send_file(
        file_path,
        as_attachment=False
    )


# =========================================================
# QR VERIFICATION
# =========================================================

@app.route(
    "/verify/<credential_id>"
)
def verify(credential_id):

    conn = get_db()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE credential_id = ?
        """,
        (
            credential_id,
        )
    ).fetchone()

    if user:

        status = "VERIFIED"

    else:

        status = "INVALID"

    conn.execute(
        """
        INSERT INTO verification_history
        (
            credential_id,
            status,
            verification_method,
            verified_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            credential_id,

            status,

            "QR",

            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )
    )

    conn.commit()

    conn.close()

    return render_template(
        "verify.html",

        user=dict(user)
        if user
        else None,

        verified=bool(user),

        credential_id=credential_id
    )


# =========================================================
# OCR TEXT CLEANING
# =========================================================

def clean_ocr_text(text):

    text = text.replace(
        "\r",
        "\n"
    )

    return text


# =========================================================
# EXTRACT VALIDATION CODE
# =========================================================

def extract_validation_code(text):

    # -----------------------------------------------------
    # First: look around VALIDATION CODE
    # -----------------------------------------------------

    validation_area_patterns = [

        r"VALIDATION\s*CODE\s*[:\-]?\s*([A-Za-z0-9]{20,64})",

        r"VALIDATION\s*CODE\s*[:\-]?\s*([A-Za-z0-9]+)",

        r"VALIDATION\s*[:\-]?\s*CODE\s*[:\-]?\s*([A-Za-z0-9]{20,64})"

    ]

    for pattern in validation_area_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            return match.group(1)

    # -----------------------------------------------------
    # Second: find 32-character hexadecimal code
    # -----------------------------------------------------

    matches = re.findall(
        r"\b[A-Fa-f0-9]{32}\b",
        text
    )

    if matches:

        return matches[0]

    # -----------------------------------------------------
    # Third: generic 32 character code
    # -----------------------------------------------------

    matches = re.findall(
        r"\b[A-Za-z0-9]{32}\b",
        text
    )

    if matches:

        return matches[0]

    return None


# =========================================================
# EXTRACT CREDENTIAL ID
# =========================================================

def extract_credential_id(text):

    patterns = [

        r"\bCRED[-\s]?\d{4}[-\s]?[A-Z0-9]+\b",

        r"\bCREDENTIAL\s*ID\s*[:\-]?\s*(CRED[-\s]?\d{4}[-\s]?[A-Z0-9]+)",

        r"\bCREDENTIAL\s*[:\-]?\s*(CRED[-\s]?\d{4}[-\s]?[A-Z0-9]+)"

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            value = match.group(1) if match.lastindex else match.group(0)

            value = value.upper()

            value = value.replace(
                " ",
                ""
            )

            return value

    return None


# =========================================================
# AI CERTIFICATE VERIFICATION
# =========================================================

@app.route(
    "/ai-verify",
    methods=["GET", "POST"]
)
def ai_verify():

    if request.method == "GET":

        return render_template(
            "ai_verify.html"
        )

    # =====================================================
    # FILE CHECK
    # =====================================================

    if "certificate" not in request.files:

        return "Certificate file not selected."

    file = request.files["certificate"]

    if file.filename == "":

        return "Please select a certificate."

    filename = secure_filename(
        file.filename
    )

    if not allowed_file(filename):

        return """
        <h2>Invalid File Type</h2>

        <p>
        Only PDF, PNG, JPG and JPEG files are allowed.
        </p>

        <a href="/ai-verify">
        Verify Another Certificate
        </a>
        """

    # =====================================================
    # UNIQUE FILE
    # =====================================================

    unique_name = (
        datetime.now().strftime(
            "%Y%m%d%H%M%S"
        )
        +
        "_"
        +
        uuid.uuid4().hex[:8]
        +
        "_"
        +
        filename
    )

    filepath = os.path.join(
        UPLOAD_FOLDER,
        unique_name
    )

    file.save(filepath)

    # =====================================================
    # OCR
    # =====================================================

    extension = filename.rsplit(
        ".",
        1
    )[-1].lower()

    extracted_text = ""

    # =====================================================
    # IMAGE OCR
    # =====================================================

    if extension in [
        "png",
        "jpg",
        "jpeg"
    ]:

        try:

            if os.path.exists(TESSERACT_PATH):

                pytesseract.pytesseract.tesseract_cmd = (
                    TESSERACT_PATH
                )

            image = Image.open(
                filepath
            ).convert("RGB")

            # ------------------------------------------------
            # OCR attempt 1 - normal image
            # ------------------------------------------------

            extracted_text = pytesseract.image_to_string(
                image,
                config="--psm 6"
            )

            # ------------------------------------------------
            # OCR attempt 2 - enhanced image
            # ------------------------------------------------

            if not extracted_text.strip():

                enhanced = ImageEnhance.Contrast(
                    image
                ).enhance(2.0)

                enhanced = enhanced.filter(
                    ImageFilter.SHARPEN
                )

                extracted_text = pytesseract.image_to_string(
                    enhanced,
                    config="--psm 6"
                )

        except Exception as e:

            extracted_text = (
                "OCR ERROR: "
                +
                str(e)
            )

    # =====================================================
    # PDF TEXT
    # =====================================================

    elif extension == "pdf":

        try:

            import fitz

            pdf_document = fitz.open(
                filepath
            )

            for page in pdf_document:

                extracted_text += (
                    page.get_text()
                    +
                    "\n"
                )

            pdf_document.close()

        except Exception as e:

            extracted_text = (
                "PDF TEXT ERROR: "
                +
                str(e)
            )

    # =====================================================
    # PRINT OCR
    # =====================================================

    print("\n")
    print("========== OCR RESULT ==========")
    print(extracted_text)
    print("================================")
    print("\n")

    # =====================================================
    # EXTRACT CREDENTIAL ID
    # =====================================================

    credential_id = extract_credential_id(
        extracted_text
    )

    # =====================================================
    # EXTRACT VALIDATION CODE
    # =====================================================

    validation_code = extract_validation_code(
        extracted_text
    )

    # =====================================================
    # PRINT DETECTION
    # =====================================================

    print("\n")
    print("========== DETECTION ==========")
    print(
        "Credential ID :",
        credential_id
    )
    print(
        "Validation Code :",
        validation_code
    )
    print("===============================")
    print("\n")

    # =====================================================
    # DATABASE SEARCH
    # =====================================================

    conn = get_db()

    user = None

    # -----------------------------------------------------
    # Search by Credential ID
    # -----------------------------------------------------

    if credential_id:

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE credential_id = ?
            """,
            (
                credential_id,
            )
        ).fetchone()

    # -----------------------------------------------------
    # Search by Validation Code
    # -----------------------------------------------------

    if validation_code and not user:

        try:

            user = conn.execute(
                """
                SELECT *
                FROM users
                WHERE validation_code = ?
                """,
                (
                    validation_code,
                )
            ).fetchone()

        except sqlite3.OperationalError:

            user = None

    # =====================================================
    # VERIFIED
    # =====================================================

    if user:

        actual_credential_id = user["credential_id"]

        relative_path = os.path.join(
            "uploads",
            unique_name
        )

        # -------------------------------------------------
        # Save certificate upload
        # -------------------------------------------------

        conn.execute(
            """
            INSERT INTO certificate_uploads
            (
                credential_id,
                filename,
                file_path,
                uploaded_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                actual_credential_id,

                filename,

                relative_path,

                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )
        )

        # -------------------------------------------------
        # Update latest certificate
        # -------------------------------------------------

        conn.execute(
            """
            UPDATE users
            SET certificate_file = ?
            WHERE credential_id = ?
            """,
            (
                relative_path,

                actual_credential_id
            )
        )

        # -------------------------------------------------
        # History
        # -------------------------------------------------

        conn.execute(
            """
            INSERT INTO verification_history
            (
                credential_id,
                status,
                verification_method,
                verified_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                actual_credential_id,

                "VERIFIED",

                "AI + OCR",

                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )
        )

        conn.commit()

        conn.close()

        return render_template(
            "ai_verified.html",

            user=dict(user),

            extracted_text=extracted_text
        )

    # =====================================================
    # INVALID
    # =====================================================

    if credential_id:

        conn.execute(
            """
            INSERT INTO verification_history
            (
                credential_id,
                status,
                verification_method,
                verified_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                credential_id,

                "INVALID",

                "AI + OCR",

                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )
        )

        conn.commit()

    conn.close()

    detected_value = (
        credential_id
        or validation_code
        or "NOT DETECTED"
    )

    return render_template(
        "ai_result.html",

        extracted_text=extracted_text,

        credential_id=detected_value
    )


# =========================================================
# VERIFICATION HISTORY
# =========================================================

@app.route(
    "/verification-history"
)
def verification_history():

    if "student_id" not in session:

        return redirect(
            url_for("home")
        )

    conn = get_db()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (
            session["student_id"],
        )
    ).fetchone()

    if not user:

        conn.close()

        return redirect(
            url_for("home")
        )

    history = conn.execute(
        """
        SELECT *
        FROM verification_history
        WHERE credential_id = ?
        ORDER BY id DESC
        """,
        (
            user["credential_id"],
        )
    ).fetchall()

    conn.close()

    return render_template(
        "verification_history.html",

        user=dict(user),

        history=[
            dict(row)
            for row in history
        ]
    )


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route(
    "/admin-login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        username = request.form.get(
            "username"
        )

        password = request.form.get(
            "password"
        )

        conn = get_db()

        admin = conn.execute(
            """
            SELECT *
            FROM admins
            WHERE username = ?
            AND password = ?
            """,
            (
                username,
                password
            )
        ).fetchone()

        conn.close()

        if admin:

            session["admin_id"] = admin["id"]

            session["admin_username"] = (
                admin["username"]
            )

            return redirect(
                url_for(
                    "admin_dashboard"
                )
            )

        return render_template(
            "admin_login.html",

            error=(
                "Invalid admin username "
                "or password."
            )
        )

    return render_template(
        "admin_login.html"
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route(
    "/admin-dashboard"
)
def admin_dashboard():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    total_users = conn.execute(
        """
        SELECT COUNT(*)
        FROM users
        """
    ).fetchone()[0]

    total_credentials = conn.execute(
        """
        SELECT COUNT(*)
        FROM users
        WHERE credential_id IS NOT NULL
        """
    ).fetchone()[0]

    total_verified = conn.execute(
        """
        SELECT COUNT(*)
        FROM verification_history
        WHERE status = 'VERIFIED'
        """
    ).fetchone()[0]

    total_invalid = conn.execute(
        """
        SELECT COUNT(*)
        FROM verification_history
        WHERE status = 'INVALID'
        """
    ).fetchone()[0]

    total_uploaded = conn.execute(
        """
        SELECT COUNT(*)
        FROM certificate_uploads
        """
    ).fetchone()[0]

    conn.close()

    return render_template(
        "admin_dashboard.html",

        total_users=total_users,

        total_credentials=total_credentials,

        total_verified=total_verified,

        total_invalid=total_invalid,

        total_uploaded=total_uploaded
    )


# =========================================================
# ADMIN CREDENTIALS
# =========================================================

@app.route(
    "/admin-credentials"
)
def admin_credentials():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    users = conn.execute(
        """
        SELECT *
        FROM users
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin_credentials.html",

        users=[
            dict(row)
            for row in users
        ]
    )


# =========================================================
# ADMIN CERTIFICATES
# =========================================================

@app.route(
    "/admin-certificates"
)
def admin_certificates():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    certificates = conn.execute(
        """
        SELECT *
        FROM users
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin_certificates.html",

        certificates=[
            dict(row)
            for row in certificates
        ]
    )


# =========================================================
# ADMIN ALL UPLOADS
# =========================================================

@app.route(
    "/admin-uploads"
)
def admin_uploads():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    uploads = conn.execute(
        """
        SELECT
            certificate_uploads.*,
            users.name,
            users.email
        FROM certificate_uploads

        LEFT JOIN users

        ON certificate_uploads.credential_id
        = users.credential_id

        ORDER BY certificate_uploads.id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin_uploads.html",

        uploads=[
            dict(row)
            for row in uploads
        ]
    )


# =========================================================
# ADMIN HISTORY
# =========================================================

@app.route(
    "/admin-history"
)
def admin_history():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    history = conn.execute(
        """
        SELECT *
        FROM verification_history
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin_history.html",

        history=[
            dict(row)
            for row in history
        ]
    )


# =========================================================
# ADMIN REGISTER ORIGINAL CERTIFICATE
# =========================================================

@app.route(
    "/admin-register-certificate",
    methods=["GET", "POST"]
)
def admin_register_certificate():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    users = conn.execute(
        """
        SELECT *
        FROM users
        ORDER BY name ASC
        """
    ).fetchall()

    if request.method == "GET":

        conn.close()

        return render_template(
            "admin_register_certificate.html",

            users=[
                dict(row)
                for row in users
            ]
        )

    # =====================================================
    # GET FORM DATA
    # =====================================================

    student_id = request.form.get(
        "student_id"
    )

    file = request.files.get(
        "certificate"
    )

    if not student_id:

        conn.close()

        return render_template(
            "admin_register_certificate.html",

            users=[
                dict(row)
                for row in users
            ],

            error="Please select a student."
        )

    if not file or file.filename == "":

        conn.close()

        return render_template(
            "admin_register_certificate.html",

            users=[
                dict(row)
                for row in users
            ],

            error="Please select the original certificate."
        )

    filename = secure_filename(
        file.filename
    )

    if not allowed_file(filename):

        conn.close()

        return render_template(
            "admin_register_certificate.html",

            users=[
                dict(row)
                for row in users
            ],

            error="Only PDF, PNG, JPG and JPEG files are allowed."
        )

    # =====================================================
    # STUDENT
    # =====================================================

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (
            student_id,
        )
    ).fetchone()

    if not user:

        conn.close()

        return render_template(
            "admin_register_certificate.html",

            users=[
                dict(row)
                for row in users
            ],

            error="Student not found."
        )

    # =====================================================
    # SAVE FILE
    # =====================================================

    unique_name = (
        "ORIGINAL_"
        +
        datetime.now().strftime(
            "%Y%m%d%H%M%S"
        )
        +
        "_"
        +
        uuid.uuid4().hex[:8]
        +
        "_"
        +
        filename
    )

    filepath = os.path.join(
        UPLOAD_FOLDER,
        unique_name
    )

    file.save(filepath)

    # =====================================================
    # OCR
    # =====================================================

    extracted_text = ""

    extension = filename.rsplit(
        ".",
        1
    )[-1].lower()

    if extension in [
        "png",
        "jpg",
        "jpeg"
    ]:

        try:

            if os.path.exists(TESSERACT_PATH):

                pytesseract.pytesseract.tesseract_cmd = (
                    TESSERACT_PATH
                )

            image = Image.open(
                filepath
            ).convert("RGB")

            extracted_text = pytesseract.image_to_string(
                image,
                config="--psm 6"
            )

        except Exception as e:

            extracted_text = (
                "OCR ERROR: "
                +
                str(e)
            )

    elif extension == "pdf":

        try:

            import fitz

            pdf_document = fitz.open(
                filepath
            )

            for page in pdf_document:

                extracted_text += (
                    page.get_text()
                    +
                    "\n"
                )

            pdf_document.close()

        except Exception as e:

            extracted_text = (
                "PDF TEXT ERROR: "
                +
                str(e)
            )

    # =====================================================
    # EXTRACT VALIDATION CODE
    # =====================================================

    validation_code = extract_validation_code(
        extracted_text
    )

    # =====================================================
    # EXTRACT CREDENTIAL ID
    # =====================================================

    detected_credential_id = extract_credential_id(
        extracted_text
    )

    # =====================================================
    # DEBUG
    # =====================================================

    print("\n")
    print("========== ADMIN OCR ==========")
    print(extracted_text)
    print("===============================")

    print(
        "Validation Code :",
        validation_code
    )

    print(
        "Credential ID :",
        detected_credential_id
    )

    print("===============================")
    print("\n")

    # =====================================================
    # IF VALIDATION CODE NOT DETECTED
    # =====================================================

    if not validation_code:

        conn.close()

        return render_template(
            "admin_register_certificate.html",

            users=[
                dict(row)
                for row in users
            ],

            error=(
                "Validation code was not detected. "
                "Make sure Tesseract is installed and "
                "try the original image."
            ),

            extracted_text=extracted_text
        )

    # =====================================================
    # SAVE VALIDATION CODE TO STUDENT
    # =====================================================

    conn.execute(
        """
        UPDATE users
        SET validation_code = ?
        WHERE id = ?
        """,
        (
            validation_code,
            student_id
        )
    )

    # =====================================================
    # SAVE UPLOAD
    # =====================================================

    relative_path = os.path.join(
        "uploads",
        unique_name
    )

    conn.execute(
        """
        INSERT INTO certificate_uploads
        (
            credential_id,
            filename,
            file_path,
            uploaded_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            user["credential_id"],

            filename,

            relative_path,

            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )
    )

    # =====================================================
    # UPDATE USER CERTIFICATE FILE
    # =====================================================

    conn.execute(
        """
        UPDATE users
        SET certificate_file = ?
        WHERE id = ?
        """,
        (
            relative_path,
            student_id
        )
    )

    conn.commit()

    conn.close()

    return render_template(
        "admin_register_certificate.html",

        users=[
            dict(row)
            for row in users
        ],

        success=(
            "Original certificate registered successfully."
        ),

        detected_validation_code=validation_code,

        detected_credential_id=(
            detected_credential_id
            or user["credential_id"]
        ),

        extracted_text=extracted_text
    )


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.route(
    "/admin-logout"
)
def admin_logout():

    session.pop(
        "admin_id",
        None
    )

    session.pop(
        "admin_username",
        None
    )

    return redirect(
        url_for("admin_login")
    )


# =========================================================
# STUDENT LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("home")
    )


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    create_database()

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
