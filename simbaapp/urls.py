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
    path('course/join/', views.join_course_view, name='join_course'),  
]
