import asyncio
import os
import random
import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from aiosmtplib import SMTP
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, datetime
from database import get_db_connection
from auth import hash_password, verify_password
from models import EmployeeLogin, EmployeeRegister, ProfileData

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info("CORS middleware configured")

# OTP Storage
otp_storage = {}
logger.info("OTP storage initialized")

# Uploads folder
UPLOADS = "uploads"
os.makedirs(UPLOADS, exist_ok=True)
logger.info(f"Uploads directory ensured: {UPLOADS}")

# SMTP Configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_USER = "quantamqlabs1@gmail.com"
SMTP_PASSWORD = "hqnd lepo ifde bmel"  # App Password
logger.info("SMTP configuration loaded")

# Helper: Send Email Asynchronously
async def send_email(to_email: str, subject: str, message: str) -> bool:
    logger.info(f"Sending email to {to_email} with subject: {subject}")
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(message, "plain"))
        smtp = SMTP(hostname=SMTP_SERVER, port=SMTP_PORT, use_tls=True)
        await smtp.connect()
        await smtp.login(SMTP_USER, SMTP_PASSWORD)
        await smtp.send_message(msg)
        await smtp.quit()
        logger.info(f"Email sent successfully to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)} - Type: {type(e).__name__}")
        return False

# Helper: OTP Expiry
def is_otp_expired(email: str) -> bool:
    logger.debug(f"Checking OTP expiry for {email}")
    if email in otp_storage:
        timestamp = otp_storage[email]["timestamp"]
        if (datetime.now().timestamp() - timestamp) > 300:
            logger.warning(f"OTP expired for {email}")
            del otp_storage[email]
            return True
    return False

# --- MODELS ---
class JobPost(BaseModel):
    id: Optional[int] = None
    title: str
    company: str
    location: str
    experience: str
    salary: str
    jobType: str
    workMode: str
    skills: List[str]
    description: str
    postedDate: Optional[date] = None
    deadline: date
    applicants: int = 0

class ResumeRegister(BaseModel):
    candidateName: Optional[str] = None
    location: Optional[str] = None
    minSalary: Optional[str] = None
    maxSalary: Optional[str] = None
    noticePeriod: Optional[str] = None
    degree: Optional[str] = None
    university: Optional[str] = None
    fromYear: Optional[str] = None
    toYear: Optional[str] = None
    specialization: Optional[str] = None
    minExperience: Optional[str] = None
    maxExperience: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    industry: Optional[str] = None
    technicalSkills: Optional[str] = None
    softSkills: Optional[str] = None
    languages: Optional[str] = None
    certifications: Optional[str] = None
    gender: Optional[str] = None
    disability: Optional[str] = None
    category: Optional[str] = None
    resumeFreshness: Optional[str] = None

class OTPRequest(BaseModel):
    email: EmailStr

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str

class JobFilter(BaseModel):
    skillset: Optional[str] = None
    city: Optional[str] = None
    min_experience: Optional[int] = None
    work_mode: Optional[str] = None

class Candidate(BaseModel):
    id: int
    name: str
    role: str
    company: str
    experience: str
    location: str
    ctc: str
    noticePeriod: str
    degree: str
    university: str
    passingYear: str
    skills: List[str]
    gender: str
    category: str
    resumeUpdated: str

# --- ROUTES ---

@app.post("/register")
async def register(employee: EmployeeRegister):
    logger.info(f"Register attempt for email: {employee.email}")
    if employee.password != employee.confirm_password:
        logger.warning("Passwords do not match")
        raise HTTPException(status_code=400, detail="Passwords do not match")

    conn = get_db_connection()
    if not conn:
        logger.error("Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM employees WHERE email = %s", (employee.email,))
        if cursor.fetchone():
            logger.warning(f"Email {employee.email} already registered")
            raise HTTPException(status_code=400, detail="Email already exists")

        hashed_password = hash_password(employee.password)
        cursor.execute(
            "INSERT INTO employees (full_name, email, password) VALUES (%s, %s, %s)",
            (employee.full_name, employee.email, hashed_password)
        )
        conn.commit()
        logger.info(f"User {employee.email} registered successfully")
        return {"message": "User registered successfully"}
    finally:
        cursor.close()
        conn.close()

@app.post("/login")
async def login(employee: EmployeeLogin):
    logger.info(f"Login attempt for email: {employee.email}")
    conn = get_db_connection()
    if not conn:
        logger.error("Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM employees WHERE email = %s", (employee.email,))
        user = cursor.fetchone()
        if not user or not verify_password(employee.password, user["password"]):
            logger.warning(f"Invalid login attempt for {employee.email}")
            raise HTTPException(status_code=401, detail="Invalid email or password")
        logger.info(f"User {employee.email} logged in successfully")
        return {"message": "Login successful", "email": employee.email}
    finally:
        cursor.close()
        conn.close()

@app.post("/send-otp")
async def send_otp(request: OTPRequest):
    logger.info(f"OTP request for email: {request.email}")
    conn = get_db_connection()
    if not conn:
        logger.error("Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM employees WHERE email = %s", (request.email,))
        user = cursor.fetchone()
        if not user:
            logger.warning(f"Email {request.email} not registered")
            raise HTTPException(status_code=404, detail="Email not registered")
        otp = f"{random.randint(0, 999999):06d}"
        otp_storage[request.email] = {"otp": otp, "timestamp": datetime.now().timestamp()}
        subject = "Your OTP for Login"
        message = f"Your OTP code is: {otp}.\n\nIt is valid for 5 minutes."
        if await send_email(request.email, subject, message):
            logger.info(f"OTP sent successfully to {request.email}")
            return {"message": "OTP sent successfully"}
        else:
            logger.error(f"Failed to send OTP to {request.email}")
            raise HTTPException(status_code=500, detail="Failed to send OTP")
    except Exception as e:
        logger.error(f"Error in send_otp for {request.email}: {str(e)} - Type: {type(e).__name__}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@app.post("/verify-otp")
async def verify_otp(request: VerifyOTPRequest):
    logger.info(f"OTP verification attempt for email: {request.email}")
    if is_otp_expired(request.email):
        logger.warning(f"OTP expired for {request.email}")
        raise HTTPException(status_code=400, detail="OTP expired")

    if request.email not in otp_storage or otp_storage[request.email]["otp"] != request.otp:
        logger.warning(f"Invalid OTP for {request.email}")
        raise HTTPException(status_code=400, detail="Invalid OTP")

    del otp_storage[request.email]
    logger.info(f"OTP verified successfully for {request.email}")
    return {"message": "Login successful"}

@app.post("/forgot-password")
async def forgot_password(request: OTPRequest):
    logger.info(f"Password reset OTP request for email: {request.email}")
    conn = get_db_connection()
    if not conn:
        logger.error("Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM employees WHERE email = %s", (request.email,))
        user = cursor.fetchone()
        if not user:
            logger.warning(f"Email {request.email} not found")
            raise HTTPException(status_code=400, detail="Email not found")

        otp = f"{random.randint(0, 999999):06d}"
        otp_storage[request.email] = {"otp": otp, "timestamp": datetime.now().timestamp()}
        subject = "Password Reset OTP"
        message = f"Your OTP is: {otp}.\n\nIt is valid for 5 minutes."

        if await send_email(request.email, subject, message):
            logger.info(f"Password reset OTP sent to {request.email}")
            return {"message": "OTP sent successfully"}
        else:
            logger.error(f"Failed to send password reset OTP to {request.email}")
            raise HTTPException(status_code=500, detail="Failed to send OTP")
    finally:
        cursor.close()
        conn.close()

@app.post("/reset-password")
async def reset_password(request: ResetPasswordRequest):
    logger.info(f"Password reset attempt for email: {request.email}")
    if is_otp_expired(request.email):
        logger.warning(f"OTP expired for {request.email}")
        raise HTTPException(status_code=400, detail="OTP expired")

    if request.email not in otp_storage or otp_storage[request.email]["otp"] != request.otp:
        logger.warning(f"Invalid OTP for password reset: {request.email}")
        raise HTTPException(status_code=400, detail="Invalid OTP")

    conn = get_db_connection()
    if not conn:
        logger.error("Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")
    cursor = conn.cursor()
    try:
        hashed_password = hash_password(request.new_password)
        cursor.execute("UPDATE employees SET password = %s WHERE email = %s", (hashed_password, request.email))
        conn.commit()
        logger.info(f"Password updated for {request.email}")
        del otp_storage[request.email]
        return {"message": "Password reset successful"}
    finally:
        cursor.close()
        conn.close()

@app.post("/search")
async def search_jobs(filter: JobFilter):
    logger.info("Job search request received")
    if not any([filter.skillset, filter.city, filter.min_experience, filter.work_mode]):
        logger.warning("No filters provided for job search")
        raise HTTPException(status_code=400, detail="At least one filter must be provided")

    conn = get_db_connection()
    if not conn:
        logger.error("Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")
    cursor = conn.cursor(dictionary=True)
    try:
        query = "SELECT * FROM jobs WHERE 1=1"
        params = []
        if filter.skillset:
            query += " AND skillset LIKE %s"
            params.append(f"%{filter.skillset}%")
        if filter.city:
            query += " AND city = %s"
            params.append(filter.city)
        if filter.min_experience is not None:
            query += " AND experience >= %s"
            params.append(filter.min_experience)
        if filter.work_mode:
            query += " AND work_mode = %s"
            params.append(filter.work_mode)

        cursor.execute(query, params)
        jobs = cursor.fetchall()
        if not jobs:
            logger.info("No jobs found for the provided filters")
            raise HTTPException(status_code=404, detail="No jobs found")
        logger.info(f"Found {len(jobs)} jobs matching filters")
        return {"jobs": jobs}
    finally:
        cursor.close()
        conn.close()

@app.post("/apply")
async def apply_for_job(
    name: str = Form(...),
    email: str = Form(...),
    job_title: str = Form(...),
    company: str = Form(...),
    resume: UploadFile = File(...)
):
    logger.info(f"Job application attempt by {email} for {job_title} at {company}")
    try:
        file_location = f"{UPLOADS}/{resume.filename}"
        with open(file_location, "wb") as buffer:
            buffer.write(await resume.read())
        logger.info(f"Resume saved at {file_location} for {email}")
        return {"message": "Application submitted", "file_saved": file_location}
    except Exception as e:
        logger.error(f"Error saving resume for {email}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving file: {str(e)}")

# Sample Job Listings
job_listings: List[JobPost] = []
logger.info("Initialized empty job listings")

@app.get("/jobs", response_model=List[JobPost])
async def get_jobs():
    logger.info("Fetching all job listings")
    return job_listings

@app.post("/post-job", response_model=JobPost)
async def post_job(job: JobPost):
    logger.info("Posting new job")
    job.id = len(job_listings) + 1
    job.postedDate = date.today()
    job_listings.insert(0, job)
    logger.info(f"Job posted successfully with ID: {job.id}")
    return job

@app.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    logger.info(f"Uploading resume: {file.filename}")
    try:
        file_location = f"{UPLOADS}/{file.filename}"
        with open(file_location, "wb") as buffer:
            buffer.write(await file.read())
        logger.info(f"Resume uploaded successfully to {file_location}")
        return {"fileName": file.filename, "message": "Resume uploaded successfully"}
    except Exception as e:
        logger.error(f"Error uploading resume {file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading resume: {str(e)}")

@app.post("/save-profile")
async def save_profile(profile: ProfileData):
    logger.info(f"Saving profile for email: {profile.email}")
    required_fields = ["firstName", "lastName", "email", "mobileNumber", "gender", "currentLocation"]
    missing_fields = [field for field in required_fields if not getattr(profile, field)]
    if missing_fields:
        logger.warning(f"Missing required fields: {', '.join(missing_fields)}")
        raise HTTPException(status_code=400, detail=f"Missing required fields: {', '.join(missing_fields)}")

    conn = get_db_connection()
    if not conn:
        logger.error("Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")
    cursor = conn.cursor()
    try:
        primary_skills_str = ",".join(profile.primarySkills) if profile.primarySkills else ""
        query = """
            INSERT INTO employee_profiles (
                avatar, first_name, last_name, email, mobile_number, gender,
                current_location, highest_qualification, university, primary_skills,
                project_details, notice_period, preferred_salary, address,
                physically_challenged, preferred_location, current_ctc, visa, resume_file_name
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                avatar=VALUES(avatar),
                first_name=VALUES(first_name),
                last_name=VALUES(last_name),
                mobile_number=VALUES(mobile_number),
                gender=VALUES(gender),
                current_location=VALUES(current_location),
                highest_qualification=VALUES(highest_qualification),
                university=VALUES(university),
                primary_skills=VALUES(primary_skills),
                project_details=VALUES(project_details),
                notice_period=VALUES(notice_period),
                preferred_salary=VALUES(preferred_salary),
                address=VALUES(address),
                physically_challenged=VALUES(physically_challenged),
                preferred_location=VALUES(preferred_location),
                current_ctc=VALUES(current_ctc),
                visa=VALUES(visa),
                resume_file_name=VALUES(resume_file_name)
        """
        values = (
            profile.avatar,
            profile.firstName,
            profile.lastName,
            profile.email,
            profile.mobileNumber,
            profile.gender,
            profile.currentLocation,
            profile.highestQualification,
            profile.university,
            primary_skills_str,
            profile.projectDetails,
            profile.noticePeriod,
            profile.preferredSalary,
            profile.address,
            profile.physicallyChallenged,
            profile.preferredLocation,
            profile.currentCTC,
            profile.visa,
            profile.resumeFileName
        )
        cursor.execute(query, values)
        conn.commit()
        logger.info(f"Profile saved successfully for {profile.email}")
        return {"message": "Profile saved successfully"}
    except Exception as e:
        logger.error(f"Error saving profile for {profile.email}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving profile: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@app.get("/get-profile/{email}")
async def get_profile(email: str):
    logger.info(f"Fetching profile for email: {email}")
    conn = get_db_connection()
    if not conn:
        logger.error("Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM employee_profiles WHERE email = %s", (email,))
        profile = cursor.fetchone()
        if not profile:
            logger.warning(f"Profile not found for {email}")
            raise HTTPException(status_code=404, detail="Profile not found")

        profile["primarySkills"] = profile["primary_skills"].split(",") if profile["primary_skills"] else []
        del profile["primary_skills"]
        logger.info(f"Profile retrieved successfully for {email}")
        return profile
    except Exception as e:
        logger.error(f"Error retrieving profile for {email}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving profile: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@app.get("/profiles", response_model=List[Candidate])
async def get_profiles():
    logger.info("Fetching all candidate profiles")
    conn = get_db_connection()
    if not conn:
        logger.error("Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT 
                id, 
                CONCAT(first_name, ' ', last_name) as name,
                'Unknown' as role,
                'Unknown' as company,
                '0 years' as experience,
                current_location as location,
                current_ctc as ctc,
                notice_period as noticePeriod,
                highest_qualification as degree,
                university,
                'Unknown' as passingYear,
                primary_skills as skills,
                gender,
                'General' as category,
                NOW() as resumeUpdated
            FROM employee_profiles
        """
        cursor.execute(query)
        profiles = cursor.fetchall()
        for profile in profiles:
            profile['skills'] = profile['skills'].split(',') if profile['skills'] else []
            profile['resumeUpdated'] = profile['resumeUpdated'].isoformat()
        logger.info(f"Retrieved {len(profiles)} candidate profiles")
        return profiles
    except Exception as e:
        logger.error(f"Error fetching profiles: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching profiles: {str(e)}")
    finally:
        cursor.close()
        conn.close()
