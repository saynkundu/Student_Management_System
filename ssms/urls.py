"""
URL configuration for ssms project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings 
from django.conf.urls.static import static
from .views import user_login,student_signup,dashboard,logout,student_list,student_details,notices,fee_payments,payment_processing,payment_success,onlineexams,teacher_login,teacher_logout,home,teacher_dashboard,upload_docs,study_materials,load_subjects,attandance,attandance_options,view_attendance,setexam,select_exam,setexam_redirect,exam_list,take_exam,exam_result,start_exam,paper_detail,generate_exam_with_ai,faculties

urlpatterns = [
    path('',home,name='home'),
    path('faculties/',faculties,name='faculties'),
    path('online-exam/<int:dys_id>/', onlineexams, name='online_exam'),
    path('exams/',exam_list, name='exam_list'),
    path('take-exam/<int:dys_id>/',take_exam, name='take_exam'),
    path('payment_success/',payment_success, name='payment_success'),
    path('payment_processing/',payment_processing,name='payment_processing'),
    path('fee_payments/',fee_payments,name='fee_payments'),
    path('notices/',notices,name='notices'),
    path('student_details/<int:student_id>/',student_details,name='student_details'),
    path('student_list/',student_list,name='student_list'),
    path('dashboard/',dashboard,name='dashboard'),
    path('user_login/',user_login,name='user_login'),
    path('student_signup/',student_signup,name='student_signup'),
    path('logout/',logout,name='logout'),
    path('study_materials/',study_materials,name='study_materials'),
    path('admin/', admin.site.urls),
    path("teacher_login/", teacher_login, name="teacher_login"),
    path("teacher_logout/", teacher_logout, name="teacher_logout"),
    path("teacher_dashboard/", teacher_dashboard, name="teacher_dashboard"),
    path("upload_docs/",upload_docs,name="upload_docs"),
    path("ajax/load-subjects/", load_subjects, name="ajax_load_subjects"),
    path("attandance/",attandance,name="attandance"),
    path("attandance_options/",attandance_options,name="attandance_options"),
    path("view_attendance/",view_attendance,name="view_attendance"),
    path('setexam/<int:dept_year_subject_id>/',setexam, name='setexam'),
    path('setexam/<int:dept_year_subject_id>/generate-ai/', generate_exam_with_ai, name='generate_exam_with_ai'),
    path('setexam_redirect/', setexam_redirect, name='setexam_redirect'),
    path('exam-result/<int:attempt_id>/', exam_result, name='exam_result'), 
    path('exam-result/', exam_result, name='exam_result_latest'),
    path('select_exam/', select_exam, name='select_exam'),
    path('paper/<int:paper_id>/start/', start_exam, name='start_exam'),
    path('paper/<int:paper_id>/', paper_detail, name='paper_detail'),
]

if settings.DEBUG: urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
