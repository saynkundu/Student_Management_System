from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from ssmsapp.models import College,Profile,Student,Notice,FeeStructure,FeePayment,Document,DepartmentYearSubject,Subject,Attendance,AttendanceSession,Option,Question,StudentExamAttempt,QuestionPaper
from django.db.models import Q,Count
from django.views.decorators.cache import never_cache
import razorpay
import json
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
import datetime
from django.core.serializers.json import DjangoJSONEncoder
from django.core.files.storage import default_storage
from ssmsapp.forms import QuestionForm, OptionFormSet, QuestionPaperForm,Question,Option
from django.urls import reverse
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone
import os
import urllib.request
import urllib.error
import re


def _resolve_groq_api_key():
    key = getattr(settings, "GROQ_API_KEY", "") or os.getenv("GROQ_API_KEY", "")
    if key:
        return key

    # Windows fallback: read user-level env var from registry (set by `setx`)
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as env_key:
                reg_value, _ = winreg.QueryValueEx(env_key, "GROQ_API_KEY")
                if reg_value:
                    return str(reg_value).strip()
        except Exception:
            pass

    return ""


def _resolve_groq_model():
    raw_model = (
        getattr(settings, "GROQ_MODEL", "")
        or os.getenv("GROQ_MODEL", "")
        or "llama-3.1-8b-instant"
    ).strip()
    return raw_model


def _format_ai_http_error(raw_error):
    if not raw_error:
        return "Unknown upstream error."

    text = raw_error.strip()

    # Try JSON error first
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            err = parsed.get("error", {})
            if isinstance(err, dict):
                message = err.get("message") or err.get("type") or str(parsed)
                code = err.get("code")
                if code:
                    return f"{message} (code: {code})"
                return str(message)
    except Exception:
        pass

    # Common Cloudflare block page signal
    if "error code: 1010" in text.lower() or "error 1010" in text.lower():
        return "Cloudflare 1010: request blocked by upstream firewall for this network/server."

    # Keep response compact if it is HTML
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:300] if cleaned else "Unknown upstream error."


def home(request):
    return render(request,'home.html')

def user_login(request): 
    if request.method == 'POST':
        roll_number = request.POST.get('roll_number')   # student enters roll number
        dob = request.POST.get('dob')                   # student enters DOB as password (YYYY-MM-DD)

        # Match roll_number and dob
        student = Student.objects.filter(roll_number=roll_number, dob=dob).first()

        if student is not None:
            request.session['student_id'] = student.id
            messages.success(request, f"Welcome back, {student.student_name}")
            return redirect('dashboard')
        else:
            messages.error(request, "Wrong Credentials")
            
    return render(request, 'students/login.html')


def student_signup(request):
    colleges = College.objects.all().order_by("name")

    if request.method == "POST":
        student_name = (request.POST.get("student_name") or "").strip()
        roll_number = (request.POST.get("roll_number") or "").strip()
        dob = request.POST.get("dob")
        photo = request.FILES.get("photo")
        college_id = request.POST.get("college")
        department = request.POST.get("department")
        year = request.POST.get("year")

        if not all([student_name, roll_number, dob, college_id, department, year]):
            messages.error(request, "Please fill all required fields.")
        elif Student.objects.filter(roll_number=roll_number).exists():
            messages.error(request, "This roll number is already registered.")
        else:
            try:
                college = College.objects.get(id=college_id)
            except College.DoesNotExist:
                messages.error(request, "Selected college is invalid.")
            else:
                student = Student.objects.create(
                    student_name=student_name,
                    roll_number=roll_number,
                    dob=dob,
                    photo=photo,
                    college_name=college,
                    department=department,
                    year=year,
                )
                request.session["student_id"] = student.id
                messages.success(request, f"Welcome, {student.student_name}")
                return redirect("dashboard")

    return render(
        request,
        "students/signup.html",
        {
            "colleges": colleges,
            "department_choices": Student.DEPARTMENT_CHOICES,
            "year_choices": Student.YEAR_CHOICES,
        },
    )


@never_cache
def dashboard(request):
    student_id = request.session.get('student_id')
    if student_id:
        student = Student.objects.get(id=student_id)
        response = render(request, 'students/dashboard.html', {'student': student})
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    else:
        return redirect('user_login')


def logout(request):
    request.session.flush()
    messages.info(request, "You have been logged out.")
    return redirect('user_login')


@never_cache
def notices(request):
    notices = Notice.objects.all().order_by('-created_at')
    Notice.objects.filter(is_read=False).update(is_read=True)
    return render(request, 'students/notice.html', {
        'notices': notices,
    })


def study_materials(request):
    student_id_session = request.session.get('student_id')
    if not student_id_session:
        return redirect('user_login')
    
    logged_student = Student.objects.get(id=student_id_session)
    documents = Document.objects.filter(college=logged_student.college_name, department=logged_student.department, year=logged_student.year)
    return render(request, 'students/study_materials.html', 
                  {
                      'student': logged_student,
                      'year': logged_student.year,
                      'documents': documents,  # Update the variable name here
                  })


@never_cache
def faculties(request):
    student_id_session = request.session.get("student_id")
    if not student_id_session:
        return redirect("user_login")

    logged_student = get_object_or_404(Student, id=student_id_session)

    teachers = (
        Profile.objects.select_related("user", "college")
        .filter(college=logged_student.college_name)
        .exclude(user__is_superuser=True)
        .order_by("user__username")
    )

    return render(
        request,
        "students/faculties.html",
        {
            "student": logged_student,
            "teachers": teachers,
        },
    )
@never_cache
def fee_payments(request):
    payment_done = ''
    student_id_session = request.session.get('student_id')
    if not student_id_session:
        return redirect('user_login')

    logged_student = Student.objects.get(id=student_id_session)

    try:
        fee_structure = FeeStructure.objects.get(
            college=logged_student.college_name,
            department=logged_student.department,
            year=logged_student.year
        )
        amount = fee_structure.total_fees
    except FeeStructure.DoesNotExist:
        amount = 0

    payment_done = FeePayment.objects.filter(
        student=logged_student,
        year=logged_student.year,
        payment_status=True
    ).exists()
    # ✅ Fetch payment history
    payment_history = FeePayment.objects.filter(
        student=logged_student,
        payment_status=True
    ).order_by('-payment_date')

    return render(request, 'students/fee_payments.html', {
        'student': logged_student,
        'year': logged_student.year,
        'amount': amount,
        'payment_done': payment_done,
        'payment_history': payment_history
    })

def payment_processing(request):
    student_id = request.session.get('student_id')
    if not student_id:
        return redirect('user_login')

    student = Student.objects.get(id=student_id)

    # ❌ Prevent double payment for same academic year
    if FeePayment.objects.filter(
        student=student,
        year=student.year,
        payment_status=True
    ).exists():
        messages.warning(request, "Fees already paid for this academic year.")
        return redirect('fee_payments')

    # ✅ Fee must always come from server
    try:
        fee = FeeStructure.objects.get(
            college=student.college_name,
            department=student.department,
            year=student.year
        )
    except FeeStructure.DoesNotExist:
        messages.error(request, "Fee structure not set. Contact admin.")
        return redirect('fee_payments')

    amount_paise = int(fee.total_fees * 100)  # Razorpay uses paise

    # ✅ Razorpay client
    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )

    # ✅ Create Razorpay Order
    order = client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "payment_capture": 1
    })

    # ✅ Create DB record (PENDING + order_id stored)
    FeePayment.objects.create(
        student=student,
        roll_number=student.roll_number,
        college=student.college_name,
        department=student.department,
        year=student.year,
        amount=fee.total_fees,
        razorpay_order_id=order["id"],
        payment_status=False
    )

    return render(request, "students/razorpay_checkout.html", {
        "razorpay_key": settings.RAZORPAY_KEY_ID,
        "order_id": order["id"],
        "amount": amount_paise,
        "student": student
    })

@csrf_exempt
def payment_success(request):
    if request.method != "POST":
        return JsonResponse({"status": "invalid"}, status=400)

    data = json.loads(request.body)

    razorpay_payment_id = data.get("razorpay_payment_id")
    razorpay_order_id = data.get("razorpay_order_id")
    razorpay_signature = data.get("razorpay_signature")

    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )

    try:
        # ✅ Verify Razorpay signature
        client.utility.verify_payment_signature({
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_order_id": razorpay_order_id,
            "razorpay_signature": razorpay_signature
        })

        payment = FeePayment.objects.get(
            razorpay_order_id=razorpay_order_id,
            payment_status=False
        )

        payment.razorpay_payment_id = razorpay_payment_id
        payment.razorpay_signature = razorpay_signature
        payment.payment_status = True
        payment.save()

        return JsonResponse({"status": "success"})

    except FeePayment.DoesNotExist:
        return JsonResponse({"status": "payment_not_found"}, status=404)

    except razorpay.errors.SignatureVerificationError:
        return JsonResponse({"status": "signature_failed"}, status=400)

    except Exception as e:
        # ✅ Log unexpected errors
        print("Payment error:", e)
        return JsonResponse({"status": "failed"}, status=500)

@login_required(login_url="student_login")
def onlineexams(request, dys_id):
    # ১. শিক্ষার্থীর প্রোফাইল এবং তথ্য সংগ্রহ
    student_profile = request.user.profile
    student_college = student_profile.college
    student_dept = student_profile.department
    student_year = student_profile.year

    # ২. নির্দিষ্ট পরীক্ষার (DYS) তথ্য ডাটাবেস থেকে আনা
    dys = get_object_or_404(DepartmentYearSubject, id=dys_id)

    # ৩. সিকিউরিটি চেক: শিক্ষার্থী কি এই কলেজের, ডিপার্টমেন্টের এবং ইয়ারের?
    # (নোট: আপনার DYS মডেলে কলেজ ফিল্ড থাকলে সেটিও চেক করতে পারেন)
    if (dys.department != student_dept or str(dys.year) != str(student_year)):
        messages.error(request, "দুঃখিত! আপনি এই পরীক্ষার জন্য অনুমোদিত নন।")
        return redirect('student_dashboard')

    # ৪. এই পরীক্ষার অধীনে থাকা প্রশ্নপত্র (Paper Title) অনুযায়ী প্রশ্নগুলো আনা
    # আমরা একটি নির্দিষ্ট টাইটেলের প্রশ্নগুলো নিচ্ছি (যেমন লেটেস্টটি)
    latest_question = Question.objects.filter(dept_year_subject=dys).order_by('-created_at').first()
    
    if not latest_question:
        return render(request, "students/no_exam.html", {"message": "বর্তমানে কোন পরীক্ষা চলমান নেই।"})

    # ঐ টাইটেলের অধীনে থাকা সব প্রশ্ন ও অপশন সংগ্রহ
    # যদি টাইটেল None হয়, তাহলে সব প্রশ্ন নিন
    if not latest_question.title:
        questions = Question.objects.filter(
            dept_year_subject=dys
        ).prefetch_related('options')
    else:
        questions = Question.objects.filter(
            dept_year_subject=dys, 
            title=latest_question.title
        ).prefetch_related('options')

    if request.method == "POST":
        # এখানে উত্তর জমা দেওয়ার লজিক (Result Calculation) লিখবেন
        score = 0
        for q in questions:
            selected_option_id = request.POST.get(f'question_{q.id}')
            if selected_option_id:
                # সঠিক উত্তর কি না যাচাই
                is_correct = q.options.filter(id=selected_option_id, is_correct=True).exists()
                if is_correct:
                    score += 1
        
        # ফলাফল দেখানোর জন্য বা সেভ করার জন্য রিডাইরেক্ট
        return render(request, "students/result.html", {"score": score, "total": questions.count()})

    context = {
        "dys": dys,
        "questions": questions,
        "paper_title": latest_question.title,
        "college": student_college
    }
    return render(request, "students/online_exam.html", context)


def exam_list(request):
    student_id_session = request.session.get('student_id')
    if not student_id_session:
        return redirect('user_login')

    student = get_object_or_404(Student, id=student_id_session)

    # IDs of papers the student already attempted
    attempted_paper_ids = list(
        StudentExamAttempt.objects.filter(student=student, paper__isnull=False).values_list('paper_id', flat=True)
    )

    # Use the student's department string and year (both are CharField on Student)
    student_dept_value = getattr(student, 'department', None)
    student_year_value = getattr(student, 'year', None)

    # Base queryset: papers for the student's department (string) and year
    base_qs = QuestionPaper.objects.filter(
        dept_year_subject__department=student_dept_value,
        dept_year_subject__year=student_year_value
    )

    # Exclude papers already attempted by this student
    if attempted_paper_ids:
        base_qs = base_qs.exclude(id__in=attempted_paper_ids)

    base_qs = base_qs.select_related('dept_year_subject__subject')

    today = timezone.localdate()

    # Show only currently running exams for today so previous records are not listed here.
    live_exams = (
        base_qs.filter(is_active=True, started_at__date=today)
        .annotate(question_count=Count('questions'))
        .order_by('-started_at')
    )
    upcoming_exams = QuestionPaper.objects.none()

    return render(request, "students/exam_list.html", {
        "student": student,
        "live_exams": live_exams,
        "upcoming_exams": upcoming_exams,
    })


def take_exam(request, dys_id):
    student_id_session = request.session.get('student_id')
    if not student_id_session:
        return redirect('user_login')

    student = get_object_or_404(Student, id=student_id_session)
    dys = get_object_or_404(DepartmentYearSubject, id=dys_id)

    # Security: ensure student belongs to this department/year
    if dys.department != student.department or dys.year != student.year:
        return render(request, "students/error.html", {"message": "You are not authorized for this exam."})

    # --- NEW: find the active paper for this DYS ---
    # If you allow only one paper per DYS to be active at a time, pick the latest active one.
    active_paper = QuestionPaper.objects.filter(
        dept_year_subject_id=dys.id,
        is_active=True
    ).order_by('-started_at').prefetch_related('questions__options').first()

    if not active_paper:
        # No active paper: show a friendly message (or redirect)
        return render(request, "students/no_exam.html", {
            "student": student,
            "message": "This exam has not been started by the teacher yet. Please wait until the teacher starts the exam."
        })

    # Use questions from the active paper only
    questions_qs = active_paper.questions.prefetch_related('options').order_by('id')
    if not questions_qs.exists():
        return render(request, "students/no_exam.html", {"student": student, "message": "No questions available for this exam."})

    # If student already attempted this active paper, redirect to result
    existing = StudentExamAttempt.objects.filter(student=student, paper=active_paper).first()
    if existing:
        return redirect(reverse('exam_result', args=[existing.id]))

    # Title from the paper
    paper_title = active_paper.title or "Untitled Exam"

    if request.method == "POST":
        # Ensure intentional submit
        if 'submit_exam' not in request.POST:
            messages.warning(request, "Submission not detected.")
            return redirect(reverse('take_exam', args=[dys_id]))

        total_marks = 0
        obtained_marks = 0
        answers = {}
        any_answered = False

        for q in questions_qs:
            total_marks += q.marks or 1
            selected = request.POST.get(f"question_{q.id}")
            answers[str(q.id)] = selected
            if selected:
                any_answered = True
                try:
                    opt = q.options.get(id=int(selected))
                    if opt.is_correct:
                        obtained_marks += q.marks or 1
                except (Option.DoesNotExist, ValueError):
                    pass

        if not any_answered:
            messages.warning(request, "You submitted without answering any question. Please answer at least one question.")
            return redirect(reverse('take_exam', args=[dys_id]))

        # Save attempt
        attempt = StudentExamAttempt.objects.create(
            student=student,
            dys=dys,
            paper=active_paper,
            score=obtained_marks,
            total=total_marks,
            answers_json=answers
        )

        return redirect(reverse('exam_result', args=[attempt.id]))

    return render(request, "students/take_exam.html", {
        "student": student,
        "dys": dys,
        "questions": questions_qs,
        "paper_title": paper_title,
        "paper": active_paper,
    })



def exam_result(request, attempt_id=None):
    # Ensure student is logged in via session
    student_id_session = request.session.get('student_id')
    if not student_id_session:
        return redirect('user_login')

    student = get_object_or_404(Student, id=student_id_session)

    if request.method == "POST" and request.POST.get("clear_attempts") == "1":
        deleted_count, _ = StudentExamAttempt.objects.filter(student=student).delete()
        if deleted_count:
            messages.success(request, "All attempted exam records have been cleared.")
        else:
            messages.info(request, "No attempted exam records found to clear.")
        return redirect("exam_result_latest")

    attempts = StudentExamAttempt.objects.filter(student=student).select_related(
        'dys__subject', 'paper'
    ).order_by('-attempted_at')

    # Fetch attempt: specific or latest
    if attempt_id:
        attempt = get_object_or_404(StudentExamAttempt, id=attempt_id)
        if attempt.student_id != student.id:
            return render(request, "students/error.html", {"message": "You are not authorized to view this result."})
    else:
        attempt = attempts.first()
        if not attempt:
            return render(
                request,
                "students/exam_result.html",
                {
                    "attempt": None,
                    "student": student,
                    "dys": None,
                    "percent": 0,
                    "attempt_rows": [],
                },
            )

    # Compute percentage safely (0-100)
    percent = 0
    try:
        if attempt.total and attempt.total > 0:
            percent = round((attempt.score / attempt.total) * 100, 1)
    except Exception:
        percent = 0

    # Build attendance stats per subject so each exam row can show
    # classes attended vs total classes happened.
    attendance_by_subject = {}
    subject_ids = attempts.values_list('dys__subject_id', flat=True).distinct()
    for subject_id in subject_ids:
        sessions_qs = AttendanceSession.objects.filter(
            college=student.college_name,
            department=student.department,
            year=student.year,
            subject_id=subject_id,
        )
        total_classes = sessions_qs.count()
        attended_classes = Attendance.objects.filter(
            attendance_session__in=sessions_qs,
            student=student,
            status=True,
        ).count()
        attendance_by_subject[subject_id] = {
            "attended_classes": attended_classes,
            "total_classes": total_classes,
        }

    attempt_rows = []
    for item in attempts:
        stats = attendance_by_subject.get(item.dys.subject_id, {"attended_classes": 0, "total_classes": 0})
        attempt_rows.append({
            "attempt": item,
            "attended_classes": stats["attended_classes"],
            "total_classes": stats["total_classes"],
        })

    context = {
        "attempt": attempt,
        "student": student,
        "dys": attempt.dys if attempt else None,
        "percent": percent,
        "attempt_rows": attempt_rows,
    }
    return render(request, "students/exam_result.html", context)


def teacher_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)  
            return redirect("teacher_dashboard")
        else:
            messages.error(request, "Invalid username or password")

    return render(request, "teachers/teacher_login.html")



def teacher_logout(request):
    logout(request)  
    return redirect("teacher_login")

@login_required(login_url="teacher_login")
def teacher_dashboard(request):
    user_profile = request.user.profile
    
    context = {
        'profile': user_profile,
        'college': user_profile.college,
    }
    return render(request, "teachers/teacher_dashboard.html", context)


@never_cache
@login_required(login_url="teacher_login")
def student_list(request): 
    department=request.GET.get('department')
    year=request.GET.get('year')
    query = request.GET.get('search')
    user_profile = request.user.profile

    # Base queryset: only same college, dept, year
    base_qs = Student.objects.filter(
        college_name=request.user.profile.college,)
    
    if department:
        dept_filtered_qs = base_qs.filter(department=department)
        if dept_filtered_qs.exists():
             students_to_show = dept_filtered_qs
        else:
            students_to_show = Student.objects.none()
            messages.error(request, "No records found")
    if year:
        year_filtered_qs = base_qs.filter(year=year)
        if year_filtered_qs.exists():
            students_to_show = year_filtered_qs
        else:
            students_to_show = Student.objects.none()
            messages.error(request, "No records found")
    if query:
        searches = base_qs.filter(
            Q(student_name__icontains=query) | Q(roll_number__icontains=query)
        )
        if searches.exists():
            students_to_show = searches
        else:
            students_to_show = Student.objects.none()
            messages.error(request, "No records found")
    else:
        students_to_show = base_qs
        searches = None
    
    return render(request, 'students/student_list.html', {
        'students': students_to_show, 
        'searches': searches,
        'college': user_profile.college
    })

@never_cache
@login_required(login_url="teacher_login")
def student_details(request, student_id):
    student = Student.objects.get(id=student_id)
    return render(request, 'students/student_details.html', {'student': student})


@login_required(login_url="teacher_login")
@never_cache
def upload_docs(request):

    if request.method == "POST":
        department = request.POST.get("department")
        year = request.POST.get("year")
        subject_id = request.POST.get("subject")

        if not department or not year or not subject_id:
            messages.error(request, "Department, Year and Subject required")
            return redirect("upload_docs")

        # Validate subject belongs to department + year
        valid_mapping = DepartmentYearSubject.objects.filter(
            department=department,
            year=year,
            subject_id=subject_id
        ).exists()

        if not valid_mapping:
            messages.error(request, "Invalid Subject selection")
            return redirect("upload_docs")

        file = request.FILES.get("file")

        if not file:
            messages.error(request, "File is required")
            return redirect("upload_docs")

        doc = Document.objects.create(
            college=request.user.profile.college,
            uploaded_by=request.user,
            department=department,
            year=year,
            subject_id=subject_id,
            title=request.POST.get("title"),
            description=request.POST.get("description"),
            file=file
        )

        if not default_storage.exists(doc.file.name):
            messages.error(
                request,
                "Upload saved in DB, but file not found on active storage backend."
            )
        else:
            messages.success(request, "Document uploaded successfully")
        return redirect("upload_docs")

    user_documents = Document.objects.filter(uploaded_by=request.user).select_related("subject")

    return render(request, "teachers/upload_docs.html", {
        "user_documents": user_documents
    })

def load_subjects(request):
    department = request.GET.get("department")
    year = request.GET.get("year")

    subjects = DepartmentYearSubject.objects.filter(
        department=department,
        year=year
    ).select_related("subject")

    data = [
        {
            "id": dys.subject.id,
            "name": f"{dys.subject.code} - {dys.subject.name}"
        }
        for dys in subjects
    ]

    return JsonResponse(data, safe=False)


@never_cache
@login_required(login_url="teacher_login")
def view_attendance(request):
    attendance_records = None
    session = None
    subjects = Subject.objects.none()

    # প্রাথমিক ভেরিয়েবল সেট করা (GET এবং POST উভয় ক্ষেত্রে দরকার)
    department = request.POST.get("department") if request.method == "POST" else request.GET.get("department")
    year = request.POST.get("year") if request.method == "POST" else request.GET.get("year")
    subject_id = request.POST.get("subject")
    selected_date = request.POST.get("date")

    # যদি ডিপার্টমেন্ট এবং ইয়ার থাকে, তবে সংশ্লিষ্ট সাবজেক্টগুলো লোড করুন
    if department and year:
        # এরর মেসেজ অনুযায়ী 'dept_year_subjects' এর মাধ্যমে ফিল্টার করা হচ্ছে
        subjects = Subject.objects.filter(
            dept_year_subjects__department=department,
            dept_year_subjects__year=year
        ).distinct()

    if request.method == "POST":
        if not department or not year or not subject_id or not selected_date:
            messages.error(request, "All fields are required.")
        else:
            # সাবজেক্ট ভ্যালিডেশন
            subject = get_object_or_404(
                Subject,
                id=subject_id,
                dept_year_subjects__department=department,
                dept_year_subjects__year=year
            )

            # অ্যাটেনডেন্স সেশন খোঁজা
            session = AttendanceSession.objects.filter(
                college=request.user.profile.college,
                department=department,
                year=year,
                subject=subject,
                date=selected_date
            ).first()

            if not session:
                messages.warning(request, "No attendance found for selected date.")
            else:
                attendance_records = Attendance.objects.filter(
                    attendance_session=session
                ).select_related("student")

    context = {
        "subjects": subjects,
        "attendance_records": attendance_records,
        "selected_department": department,
        "selected_year": year,
        "selected_subject": subject_id,
        "selected_date": selected_date,
        "session": session,
    }
    return render(request, "teachers/view_attendance.html", context)


@never_cache
@login_required(login_url="teacher_login")
def attandance_options(request):
    return render(request, "teachers/attandance_options.html")

@login_required(login_url="teacher_login")
def attandance(request):
    # টিচারের কলেজ গেট করা (আপনার প্রোফাইল মডেল অনুযায়ী)
    user_college = request.user.profile.college 
    
    department = request.POST.get("department")
    year = request.POST.get("year")
    subject_id = request.POST.get("subject")
    
    students = None
    attendance_taken = False
    subjects = Subject.objects.none()
    today = datetime.date.today()

    # ১. ড্রপডাউনের জন্য সাবজেক্ট ফিল্টার
    if department and year:
        subjects = Subject.objects.filter(
            dept_year_subjects__department=department,
            dept_year_subjects__year=year
        ).distinct()

    if request.method == "POST":
        if "save_attendance" in request.POST:
            subject = Subject.objects.get(id=subject_id)
            
            # সেশন তৈরি (এখানে ফিল্ডের নাম models.py অনুযায়ী চেক করে নিন, সাধারণত college থাকে)
            session, created = AttendanceSession.objects.get_or_create(
                college=user_college, 
                department=department,
                year=year,
                subject=subject,
                date=today,
                defaults={'taken_by': request.user}
            )

            # ✅ এখানে 'college_name' ব্যবহার করা হয়েছে (আপনার এরর অনুযায়ী)
            students_list = Student.objects.filter(
                college_name=user_college, 
                department=department, 
                year=year
            )
            
            for student in students_list:
                status_val = request.POST.get(f"status_{student.id}")
                is_present = (status_val == "present")
                
                Attendance.objects.update_or_create(
                    attendance_session=session,
                    student=student,
                    defaults={'status': is_present}
                )
            return redirect('teacher_dashboard')

        else:
            if department and year and subject_id:
                # সেশন চেক
                attendance_taken = AttendanceSession.objects.filter(
                    college=user_college,
                    department=department, 
                    year=year, 
                    subject_id=subject_id, 
                    date=today
                ).exists()

                if not attendance_taken:
                    # ✅ এখানেও 'college_name' ব্যবহার করা হয়েছে
                    students = Student.objects.filter(
                        college_name=user_college, 
                        department=department, 
                        year=year
                    )

    return render(request, "teachers/attandance_sheet.html", {
        "subjects": subjects,
        "students": students,
        "selected_department": department,
        "selected_year": year,
        "selected_subject": subject_id,
        "attendance_taken": attendance_taken,
    })



@never_cache
@login_required(login_url="teacher_login")
def setexam(request, dept_year_subject_id):
    dys = get_object_or_404(DepartmentYearSubject, id=dept_year_subject_id)

    # load paper in progress if any
    paper = None
    paper_id = request.session.get('paper_id')
    if paper_id:
        paper = QuestionPaper.objects.filter(id=paper_id, created_by=request.user).first()

    if request.method == "POST":
        # 1) Paper setup step
        if "paper_setup" in request.POST:
            paper_form = QuestionPaperForm(request.POST)
            if paper_form.is_valid():
                # create a paper record (not active yet)
                paper = paper_form.save(commit=False)
                paper.dept_year_subject = dys
                paper.created_by = request.user
                paper.is_active = False
                paper.save()
                # store paper id and expected num_questions in session
                request.session['paper_id'] = paper.id
                request.session['num_questions'] = int(paper_form.cleaned_data['num_questions'])
                return redirect('setexam', dept_year_subject_id=dys.id)
            else:
                # show form errors
                return render(request, 'teachers/setexam.html', {
                    'dys': dys,
                    'paper_form': paper_form,
                    'paper': paper,
                })

        # 2) Save questions step
        elif "save_questions" in request.POST:
            paper_id = request.session.get('paper_id')
            if not paper_id:
                return HttpResponseBadRequest("No paper in progress. Create the paper first.")
            paper = get_object_or_404(QuestionPaper, id=paper_id, created_by=request.user)
            if not paper.editable:
                return HttpResponseBadRequest("This paper is locked and cannot be edited.")

            # get number of questions (prefer session, fallback to posted value)
            num_questions = int(request.session.get('num_questions', request.POST.get('num_questions', 0)))

            with transaction.atomic():
                # optional: delete existing questions for this paper if you want replace behavior
                # paper.questions.all().delete()

                for i in range(num_questions):
                    q_text = request.POST.get(f'question_{i}')
                    correct_idx = request.POST.get(f'question_{i}_correct')
                    marks = request.POST.get(f'question_{i}_marks', 1)

                    if not q_text:
                        continue

                    q = Question.objects.create(
                        paper=paper,
                        dept_year_subject=dys,
                        text=q_text,
                        marks=int(marks) if marks else 1,
                        title=paper.title,
                        created_by=request.user
                    )

                    # create 4 options (only if provided)
                    for j in range(4):
                        opt_text = request.POST.get(f'question_{i}_option_{j}')
                        is_correct = (str(j) == str(correct_idx))
                        if opt_text:
                            q.options.create(text=opt_text, is_correct=is_correct)

                # update paper.num_questions to actual saved count
                paper.num_questions = paper.questions.count()
                paper.save()

            # keep paper_id in session so teacher can start exam from select page
            return redirect('paper_detail', paper_id=paper.id)

    else:
        paper_form = QuestionPaperForm()

    # values for template
    paper_title = request.session.get('paper_title', paper.title if paper else '')
    num_questions = request.session.get('num_questions', paper.num_questions if paper else 0)
    question_range = range(num_questions)

    return render(request, 'teachers/setexam.html', {
        'dys': dys,
        'paper_form': paper_form,
        'paper': paper,
        'paper_title': paper_title,
        'num_questions': num_questions,
        'question_range': question_range,
    })


@login_required(login_url="teacher_login")
def generate_exam_with_ai(request, dept_year_subject_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")

    dys = get_object_or_404(DepartmentYearSubject, id=dept_year_subject_id)
    topic = (request.POST.get("topic") or "").strip()
    paper_title = (request.POST.get("paper_title") or "").strip()

    try:
        requested_count = int(request.POST.get("num_questions", "0"))
    except ValueError:
        requested_count = 0

    if not topic:
        return JsonResponse({"error": "Please enter a topic."}, status=400)
    if requested_count <= 0:
        return JsonResponse({"error": "Invalid number of questions."}, status=400)

    api_key = _resolve_groq_api_key()
    model = _resolve_groq_model()
    if not api_key:
        return JsonResponse(
            {"error": "GROQ_API_KEY is not configured on the server."},
            status=500
        )

    system_prompt = (
        "You generate multiple-choice exam questions for teachers. "
        "Return only valid JSON with this exact schema: "
        "{\"questions\":[{\"question\":\"...\",\"options\":[\"...\",\"...\",\"...\",\"...\"],"
        "\"correct_index\":0,\"marks\":1}]}. "
        "Rules: exactly the requested number of questions, exactly 4 options each, "
        "single correct option, no markdown, no extra keys."
    )

    user_prompt = (
        f"Create {requested_count} MCQ questions for subject '{dys.subject.name}' "
        f"(Department: {dys.department}, Year: {dys.year}). "
        f"Paper title: '{paper_title or 'Untitled'}'. "
        f"Topic: '{topic}'. "
        "Difficulty: medium. Use concise, classroom-safe language."
    )

    base_payload = {
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    candidate_models = [model, "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
    # preserve order and remove duplicates
    seen = set()
    candidate_models = [m for m in candidate_models if not (m in seen or seen.add(m))]

    data = None
    last_error = ""
    for candidate_model in candidate_models:
        payload = dict(base_payload)
        payload["model"] = candidate_model
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "User-Agent": "SSMS-Django/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                data = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            last_error = _format_ai_http_error(e.read().decode("utf-8", errors="ignore"))
            continue
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", None)
            last_error = f"Network error while contacting AI service: {reason or e}"
            continue
        except Exception as e:
            last_error = f"Failed to contact AI service: {e}"
            continue

    if not data:
        return JsonResponse({"error": f"AI request failed: {last_error}"}, status=500)

    try:
        content = data["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.strip()
            lines = content.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()
            if content.startswith("json"):
                content = content[4:].strip()
        parsed = json.loads(content)
        generated = parsed.get("questions", [])
    except Exception:
        return JsonResponse({"error": "AI returned an unexpected format."}, status=500)

    normalized = []
    for item in generated[:requested_count]:
        q_text = (item.get("question") or "").strip()
        options = item.get("options") or []
        if len(options) != 4:
            continue
        option_texts = [(str(opt).strip() or f"Option {idx + 1}") for idx, opt in enumerate(options[:4])]
        try:
            correct_index = int(item.get("correct_index", 0))
        except (TypeError, ValueError):
            correct_index = 0
        if correct_index < 0 or correct_index > 3:
            correct_index = 0
        try:
            marks = int(item.get("marks", 1))
        except (TypeError, ValueError):
            marks = 1
        if marks < 1:
            marks = 1
        normalized.append({
            "question": q_text or "Generated question",
            "options": option_texts,
            "correct_index": correct_index,
            "marks": marks,
        })

    while len(normalized) < requested_count:
        fallback_idx = len(normalized) + 1
        normalized.append({
            "question": f"Question {fallback_idx} on {topic}",
            "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
            "correct_index": 0,
            "marks": 1,
        })

    return JsonResponse({"questions": normalized})


@never_cache
@login_required(login_url="teacher_login")
def select_exam(request):
    profile = request.user.profile
    college = profile.college
    today = timezone.localdate()

    dys_queryset = DepartmentYearSubject.objects.select_related('subject').all()
    departments = sorted(list(dys_queryset.values_list('department', flat=True).distinct()))
    dys_data = list(dys_queryset.values('id', 'department', 'year', 'subject__id', 'subject__name'))

    # Clear previous records before today for this teacher.
    QuestionPaper.objects.filter(
        created_by=request.user,
        created_at__date__lt=today
    ).delete()

    # Use QuestionPaper model to list papers created by this teacher
    past_papers = QuestionPaper.objects.filter(
        created_by=request.user,
        created_at__date=today
    ).select_related('dept_year_subject__subject').order_by('-created_at')

    context = {
        "college": college,
        "departments": departments,
        "dys_list_json": json.dumps(dys_data, cls=DjangoJSONEncoder),
        "past_papers": past_papers,
        "user": request.user,
    }
    return render(request, "teachers/select_exam.html", context)



# paper_detail: teacher view to inspect a paper
@login_required(login_url="teacher_login")
def paper_detail(request, paper_id):
    paper = get_object_or_404(QuestionPaper, id=paper_id)
    # only allow creator (teacher) to view this teacher-detail page
    if paper.created_by != request.user:
        return HttpResponseForbidden("Not allowed")

    questions = paper.questions.prefetch_related('options').all().order_by('id')
    return render(request, 'teachers/paper_detail.html', {
        'paper': paper,
        'questions': questions,
    })

# start_exam: POST endpoint to activate the paper
@login_required(login_url="teacher_login")
def start_exam(request, paper_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")

    paper = get_object_or_404(QuestionPaper, id=paper_id)

    # ownership check
    if paper.created_by != request.user:
        return HttpResponseForbidden("Not allowed")

    # prevent starting twice and prevent empty papers
    if paper.is_active:
        return HttpResponseBadRequest("Exam already started")
    if paper.questions.count() == 0:
        return HttpResponseBadRequest("Cannot start an empty paper")

    # start the exam
    paper.is_active = True
    paper.started_at = timezone.now()
    paper.editable = False
    paper.save()

    return redirect('paper_detail', paper_id=paper.id)



def setexam_redirect(request):
    subject_id = request.GET.get("subject")
    if subject_id:
        return redirect('setexam', dept_year_subject_id=subject_id)
    return redirect('select_exam')

