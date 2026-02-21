from django.db import models, transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
import os
from pathlib import PurePosixPath
from uuid import uuid4
from django.conf import settings
from django.utils.text import get_valid_filename

class College(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Subject(models.Model):
    code = models.CharField(max_length=20, unique=True)   # e.g. SUB1, ML2, IT3
    name = models.CharField(max_length=100)               # e.g. Data Structures

    def __str__(self):
        return f"{self.code} - {self.name}"


class DepartmentYearSubject(models.Model):
    DEPARTMENT_CHOICES = [
        ("CSE", "Computer Science"),
        ("IT", "Information Technology"),
        ("AIML", "Artificial Intelligence & ML"),
    ]

    YEAR_CHOICES = [
        ("1", "1st Year"),
        ("2", "2nd Year"),
        ("3", "3rd Year"),
        ("4", "4th Year"),
    ]

    department = models.CharField(max_length=10, choices=DEPARTMENT_CHOICES)
    year = models.CharField(max_length=1, choices=YEAR_CHOICES)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="dept_year_subjects")

    class Meta:
        unique_together = ("department", "year", "subject")

    def __str__(self):
        return f"{self.subject.code} ({self.department}, Year {self.year})"


class Student(models.Model):
    DEPARTMENT_CHOICES = [
        ("CSE", "Computer Science"),
        ("IT", "Information Technology"),
        ("AIML", "Artificial Intelligence & ML"),
    ]

    YEAR_CHOICES = [
        ("1", "1st Year"),
        ("2", "2nd Year"),
        ("3", "3rd Year"),
        ("4", "4th Year"),
    ]

    student_name = models.CharField(max_length=100)
    roll_number = models.CharField(max_length=20, unique=True)
    college_name = models.ForeignKey(College, on_delete=models.CASCADE)
    department = models.CharField(max_length=10, choices=DEPARTMENT_CHOICES)
    year = models.CharField(max_length=1, choices=YEAR_CHOICES)
    dob = models.DateField()
    photo = models.ImageField(upload_to="student_photos/", blank=True, null=True)  # ✅ new field

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)

            # Fetch subjects for this student's department + year
            dept_year_subjects = DepartmentYearSubject.objects.filter(
                department=self.department, year=self.year
            )

            # Assign subjects to student
            for dys in dept_year_subjects:
                StudentSubject.objects.get_or_create(student=self, subject=dys.subject)

    def __str__(self):
        return f"{self.student_name} ({self.roll_number})"



class StudentSubject(models.Model): 
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="student_subjects") 
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="student_subjects") 
    class Meta:
        unique_together = ("student", "subject") 
    def __str__(self): 
        return f"ID {self.id}: {self.student.roll_number} → {self.subject.code}"
    
class Notice(models.Model):
    title = models.CharField(max_length=100)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False) 

    def __str__(self):
        return self.title
    
class FeeStructure(models.Model):
    college = models.ForeignKey(College, on_delete=models.CASCADE)
    department = models.CharField(max_length=10, choices=Student.DEPARTMENT_CHOICES)
    year = models.CharField(max_length=1, choices=Student.YEAR_CHOICES)
    total_fees = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ("college", "department", "year")

    def __str__(self):
        return f"{self.college.name} - {self.department} ({self.year} Year) - {self.total_fees} TK"

class FeePayment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    roll_number = models.CharField(max_length=20)
    college = models.ForeignKey(College, on_delete=models.CASCADE)
    department = models.CharField(max_length=10, choices=Student.DEPARTMENT_CHOICES)
    year = models.CharField(max_length=1, choices=Student.YEAR_CHOICES)

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    # 🔐 Razorpay fields (VERY IMPORTANT)
    razorpay_order_id = models.CharField(max_length=100, unique=True)
    razorpay_payment_id = models.CharField(max_length=100, null=True, blank=True)
    razorpay_signature = models.CharField(max_length=200, null=True, blank=True)

    payment_date = models.DateTimeField(auto_now_add=True)
    payment_status = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.roll_number} | Year {self.year} | {'PAID' if self.payment_status else 'PENDING'}"

# 🔔 Signal: auto-assign new subjects to existing students
@receiver(post_save, sender=DepartmentYearSubject)
def assign_new_subject_to_students(sender, instance, created, **kwargs):
    if created:
        # Find all students in the same department + year
        students = Student.objects.filter(department=instance.department, year=instance.year)

        # Assign this new subject to each student
        for student in students:
            StudentSubject.objects.get_or_create(student=student, subject=instance.subject)

@receiver(post_delete, sender=DepartmentYearSubject)
def remove_subject_from_students(sender, instance, **kwargs):
    # Delete all StudentSubject entries for this subject
    StudentSubject.objects.filter(subject=instance.subject).delete()



class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    profile_image = models.ImageField(upload_to="profiles/", null=True, blank=True)
    college = models.ForeignKey(College, on_delete=models.CASCADE, null=True, blank=True)
    department= models.CharField(max_length=10, choices=Student.DEPARTMENT_CHOICES, null=True, blank=True)
    specialization = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.user.username
    

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


def document_upload_path(instance, filename):
    base_name = os.path.basename(filename or "document.pdf")
    safe_name = get_valid_filename(base_name)
    name_root, ext = os.path.splitext(safe_name)
    ext = ext.lower() or ".pdf"
    short_root = (name_root[:45] or "document").strip("._")
    unique_suffix = uuid4().hex[:8]
    safe_filename = f"{short_root}_{unique_suffix}{ext}"

    return str(PurePosixPath(
        "documents",
        str(instance.college.name),
        str(instance.department),
        f"Year_{instance.year}",
        safe_filename
    ))

class Document(models.Model):
    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name="documents")
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="documents")

    department = models.CharField(max_length=10, choices=Student.DEPARTMENT_CHOICES)
    year = models.CharField(max_length=1, choices=Student.YEAR_CHOICES)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    file = models.FileField(upload_to=document_upload_path, max_length=300)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.college.name} ({self.department} Year {self.year})"
    
class AttendanceSession(models.Model):
    college = models.ForeignKey(College, on_delete=models.CASCADE)

    department = models.CharField(
        max_length=10,
        choices=Student.DEPARTMENT_CHOICES
    )

    year = models.CharField(
        max_length=1,
        choices=Student.YEAR_CHOICES
    )

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)

    date = models.DateField()

    # ✅ THIS IS WHAT YOU WANT
    taken_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="attendance_taken"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("department", "year", "subject", "date")

    def __str__(self):
        return f"{self.subject.code} - {self.date} ({self.department} Year {self.year})"

class Attendance(models.Model):
    attendance_session = models.ForeignKey(
        AttendanceSession,
        on_delete=models.CASCADE,
        related_name="records"
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE
    )

    status = models.BooleanField(default=False)  # True = Present

    class Meta:
        unique_together = ("attendance_session", "student")

    def __str__(self):
        return f"{self.student.roll_number} - {self.attendance_session.date}"

# models.py
from django.db import models
from django.conf import settings
from django.utils import timezone

class QuestionPaper(models.Model):
    dept_year_subject = models.ForeignKey(DepartmentYearSubject, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    num_questions = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=False)
    started_at = models.DateTimeField(null=True, blank=True)
    editable = models.BooleanField(default=True)

    def start(self):
        if not self.is_active and self.questions.exists():
            self.is_active = True
            self.started_at = timezone.now()
            self.editable = False
            self.save()

    def __str__(self):
        return f"{self.title} ({self.created_by})"

class Question(models.Model):
    paper = models.ForeignKey(QuestionPaper, related_name="questions", on_delete=models.CASCADE, null=True, blank=True)
    dept_year_subject = models.ForeignKey(DepartmentYearSubject, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    marks = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=200, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Q{self.id}: {self.text[:50]}"

class Option(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="options"
    )
    text = models.CharField(max_length=300)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.text} ({'Correct' if self.is_correct else 'Wrong'})"
    

    
class StudentExamAttempt(models.Model):
    student = models.ForeignKey('ssmsapp.Student', on_delete=models.CASCADE)
    dys = models.ForeignKey('ssmsapp.DepartmentYearSubject', on_delete=models.CASCADE)
    paper = models.ForeignKey(
        'ssmsapp.QuestionPaper',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='attempts'
    )
    score = models.IntegerField()
    total = models.IntegerField()
    answers_json = models.JSONField()
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'paper')   # prevents multiple attempts per student per paper
        ordering = ['-attempted_at']

    def __str__(self):
        return f"{self.student} - {self.dys} - {self.score}/{self.total}"

