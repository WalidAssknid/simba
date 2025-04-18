from django.urls import path
import simbaapp.views as views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('courses/', views.courses_view, name='courses'), 
    path('chainlit/', views.chainlit_view, name='chainlit_view'),
    path('course/create/', views.create_course_view, name='create_course'), 
    path('course/<int:course_id>/', views.course_detail_view, name='course_detail'),  
    path('course/<int:course_id>/activity/create/', views.create_activity_view, name='create_activity'),  
    
    # Classroom routes
    path('classrooms/', views.classrooms_view, name='classrooms'),
    path('classroom/create/', views.create_classroom_view, name='create_classroom'),
    path('classroom/<int:classroom_id>/', views.classroom_detail_view, name='classroom_detail'),
    path('classroom/<int:classroom_id>/topic/create/', views.create_topic_view, name='create_topic'),
    path('classroom/enroll/', views.enroll_classroom_view, name='enroll_classroom'),
    path('course/join/', views.join_course_view, name='join_course'),  
]
