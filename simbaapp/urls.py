from django.urls import path
from . import views
from .api import api 
urlpatterns = [
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('profile/', views.profile_view, name='profile'),
    path('courses/', views.courses_view, name='courses'),
    path('courses/<int:course_id>/', views.course_detail_view, name='course_detail'),
    path('courses/create/', views.create_course_view, name='create_course'),
    path('courses/join/', views.join_course_view, name='join_course'),
    path('courses/<int:course_id>/edit/', views.edit_course_view, name='edit_course'),
    path('activities/', views.activities_view, name='activities'),
    path('courses/<int:course_id>/create_activity/', views.create_activity_view, name='create_activity'), 
    path('chainlit/', views.chainlit_view, name='chainlit_interface'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path("api/", api.urls), 
]
