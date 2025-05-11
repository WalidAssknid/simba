from django.urls import path
import simbaapp.views as views
import simbaapp.api as api

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('courses/', views.courses_view, name='courses'), 
    path('activities/', views.activities_view, name='activities'),
    path('chainlit/', views.chainlit_view, name='chainlit_view'),
    path('course/create/', views.create_course_view, name='create_course'), 
    path('course/<int:course_id>/', views.course_detail_view, name='course_detail'),  
    path('course/<int:course_id>/edit/', views.edit_course_view, name='edit_course'),  
    path('course/<int:course_id>/activity/create/', views.create_activity_view, name='create_activity'),  
    path('course/join/', views.join_course_view, name='join_course'),  
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # API endpoints
    path('api/course/<int:course_id>/', api.get_course_info, name='api_course_info'),
    path('api/course/<int:course_id>/participants/', api.get_course_participants, name='api_course_participants'),
]
