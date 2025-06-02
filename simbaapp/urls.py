from django.urls import path
from . import views
from .api import api 
urlpatterns = [
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('verify-email/<str:token>/', views.verify_email_view, name='verify_email'),
    path('resend-verification/', views.resend_verification_view, name='resend_verification'),
    path('password-reset-request/', views.password_reset_request_view, name='password_reset_request'),
    path('reset-password/<str:token>/', views.password_reset_view, name='password_reset'),
    path('email-verification-status/', views.email_verification_status_view, name='email_verification_status'),
    path('profile/', views.profile_view, name='profile'),
    path('courses/', views.courses_view, name='courses'),
    path('courses/create/', views.create_course_view, name='create_course'),
    path('courses/join/', views.join_course_view, name='join_course'),
    path('courses/invite/<str:token>/', views.invite_join_view, name='invite_join'),
    path('courses/<str:course_id>/', views.course_detail_view, name='course_detail'),
    path('courses/<str:course_id>/edit/', views.edit_course_view, name='edit_course'),
    path('courses/<str:course_id>/create_activity/', views.create_activity_view, name='create_activity'),
    path('activities/join/<str:token>/', views.activity_join_view, name='activity_join'),
    path('activities/', views.activities_view, name='activities'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('chainlit/', views.chainlit_view, name='chainlit'),
    path('api/', api.urls),
]
