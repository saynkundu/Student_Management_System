from django.contrib import admin
from .models import College, Subject, DepartmentYearSubject, Student, StudentSubject,Notice,FeeStructure,FeePayment,Profile,Document,Attendance,AttendanceSession,Option,Question
from django.utils.html import format_html
from django.contrib import admin

@admin.register(College)
class CollegeAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(DepartmentYearSubject)
class DepartmentYearSubjectAdmin(admin.ModelAdmin):
    list_display = ("subject", "department", "year")
    list_filter = ("department", "year")
    search_fields = ("subject__code", "subject__name")


class StudentSubjectInline(admin.TabularInline):
    model = StudentSubject
    extra = 0
    readonly_fields = ("subject",)


@admin.register(Student) 
class StudentAdmin(admin.ModelAdmin): 
    list_display = ( 
        "student_name", 
        "roll_number", 
        "college_name", 
        "department", 
        "year", 
        "dob", 
        "photo_preview", # ✅ show image preview 
        ) 
    list_filter = ("college_name", "department", "year") 
    search_fields = ("student_name", "roll_number") 
    inlines = [StudentSubjectInline] 
    def photo_preview(self, obj): 
        if obj.photo: 
            return format_html('<img src="{}" width="60" height="60" style="object-fit: cover;"/>', obj.photo.url)
        return "No Photo" 
    photo_preview.short_description = "Photo"


@admin.register(StudentSubject)
class StudentSubjectAdmin(admin.ModelAdmin):
    list_display = ("get_roll_number", "get_student_name", "get_subject_code", "get_subject_name")
    search_fields = ("student__student_name", "student__roll_number", "subject__code", "subject__name")
    ordering = ("id",)   # ✅ sort by StudentSubject ID (ascending)

    def get_roll_number(self, obj):
        return obj.student.roll_number
    get_roll_number.short_description = "Roll No"

    def get_student_name(self, obj):
        return obj.student.student_name
    get_student_name.short_description = "Name"

    def get_subject_code(self, obj):
        return obj.subject.code
    get_subject_code.short_description = "Subject Code"

    def get_subject_name(self, obj):
        return obj.subject.name
    get_subject_name.short_description = "Subject"

@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ("title","content", "created_at")

@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ('college', 'department', 'year', 'total_fees')
    list_filter = ('college', 'department', 'year') 

@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    list_display = ('student', 'roll_number', 'college', 'department', 'year', 'amount', 'payment_date', 'payment_status')



admin.site.register(Profile)

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "college",
        "department",
        "year",
        "subject",
        "uploaded_by",
        "uploaded_at",
    )
    list_filter = ("college", "department", "year",)
    search_fields = ("title", "uploaded_by__username")
    readonly_fields = ("uploaded_at",)

# 🔹 Inline Attendance Records inside Session
class AttendanceInline(admin.TabularInline):
    model = Attendance
    extra = 0
    autocomplete_fields = ['student']
    show_change_link = True


# 🔹 Attendance Session Admin
@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = (
        "subject",
        "department",
        "year",
        "date",
        "college",
        "taken_by",
        "created_at",
    )

    list_filter = (
        "department",
        "year",
        "subject",
        "date",
        "college",
    )

    search_fields = (
        "subject__name",
        "subject__code",
        "taken_by__username",
    )

    date_hierarchy = "date"

    inlines = [AttendanceInline]

    autocomplete_fields = ["subject", "taken_by", "college"]


# 🔹 Attendance Record Admin
@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "attendance_session",
        "status",
    )

    list_filter = (
        "status",
        "attendance_session__date",
        "attendance_session__subject",
    )

    search_fields = (
        "student__student_name",
        "student__roll_number",
    )

    autocomplete_fields = ["student", "attendance_session"]


from django.contrib import admin
from .models import Question, Option

# ১. অপশনগুলোকে প্রশ্নের ভেতরে ইনলাইন হিসেবে দেখানোর জন্য
class OptionInline(admin.TabularInline):
    model = Option
    extra = 4           # ডিফল্ট ৪টি অপশন বক্স দেখাবে
    max_num = 4         
    min_num = 4         
    can_delete = False  # ডিলিট অপশন বন্ধ (যাতে ভুল করে অপশন ডিলিট না হয়)

# ২. কোশ্চেন এডমিন কনফিগারেশন (আপনার ড্যাশবোর্ড রিকোয়ারমেন্ট অনুযায়ী)
@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    # ড্যাশবোর্ডে যে কলামগুলো দেখাবে (Title, College, Dept, Year, Created By, Date)
    list_display = (
        'id', 
        'text_excerpt',            # প্রশ্নের ছোট অংশ
        'get_college',             # কলেজের নাম
        'get_dept',                # ডিপার্টমেন্ট
        'get_year',                # বছর
        'get_created_by',          # কে তৈরি করেছেন
        'get_created_at'           # কখন তৈরি করেছেন (যদি মডেলে থাকে)
    )
    
    # সাইডবারে ফিল্টার করার সুবিধা
    list_filter = (
        'dept_year_subject__department', 
        'dept_year_subject__year', 
        'marks'
    )
    
    # সার্চ বক্স (টাইটেল বা টেক্সট দিয়ে খোঁজার জন্য)
    search_fields = ('text', 'dept_year_subject__subject__name')
    
    # প্রশ্নের ভেতরে অপশনগুলো ইনলাইন হিসেবে যোগ করা
    inlines = [OptionInline]

    # --- কাস্টম মেথডসমূহ (ডেটা দেখানোর জন্য) ---

    def text_excerpt(self, obj):
        """প্রশ্নের প্রথম ৫০টি অক্ষর দেখাবে"""
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text
    text_excerpt.short_description = 'Question'

    def get_college(self, obj):
        """কলেজের নাম দেখাবে (Profile মডেল থেকে)"""
        try:
            # যদি Question মডেলে 'created_by' ফিল্ড যোগ করে থাকেন
            return obj.created_by.profile.college.name
        except AttributeError:
            return "N/A"
    get_college.short_description = 'College Name'

    def get_dept(self, obj):
        """ডিপার্টমেন্ট দেখাবে"""
        return obj.dept_year_subject.department
    get_dept.short_description = 'Department'

    def get_year(self, obj):
        """বছর দেখাবে"""
        return f"Year {obj.dept_year_subject.year}"
    get_year.short_description = 'Year'

    def get_created_by(self, obj):
        """যিনি প্রশ্ন তৈরি করেছেন তার নাম"""
        try:
            return obj.created_by.get_full_name() or obj.created_by.username
        except AttributeError:
            return "Unknown"
    get_created_by.short_description = 'Created By'

    def get_created_at(self, obj):
        """তৈরির সময় (যদি মডেলে থাকে)"""
        try:
            return obj.created_at.strftime("%d %b %Y, %I:%M %p")
        except AttributeError:
            return "N/A"
    get_created_at.short_description = 'Date & Time'

# ৩. আলাদাভাবে অপশন দেখার জন্য
@admin.register(Option)
class OptionAdmin(admin.ModelAdmin):
    list_display = ('text', 'question', 'is_correct')
    list_filter = ('is_correct',)