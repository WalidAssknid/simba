from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
import urllib
import requests
from django.urls import reverse
from django.conf import settings
from .models import User, Course, Activity, CourseEnrollment, Message

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        api_url = request.build_absolute_uri(reverse('api-1.0.0:login_user')) 
        
        try:
            response = requests.post(api_url, json={
                'username': username,
                'password': password
            })
            response.raise_for_status() 
            
            user_data = response.json()
            
            request.session['user_id'] = user_data['id']
            request.session['username'] = user_data['username']
            request.session['role'] = user_data['role']
            
            return redirect('courses')
            
        except requests.exceptions.RequestException as e:
            messages.error(request, f"Login request failed: {e}")
            try:
                error_data = e.response.json()
                messages.error(request, f"API Error: {error_data.get('message', 'Unknown error')}")
            except (AttributeError, ValueError, TypeError):
                 messages.error(request, "An unexpected error occurred during login.")
        except Exception as e:
             messages.error(request, f"An unexpected error occurred: {str(e)}")

    return render(request, 'login.html')

def logout_view(request):
    request.session.flush()
    messages.success(request, "Successfully logged out!")
    return redirect('login')

def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        role = request.POST.get('role', 'student')
        
        api_url = request.build_absolute_uri(reverse('api-1.0.0:register_user'))
        
        try:
            response = requests.post(api_url, json={
                'username': username,
                'email': email,
                'password': password,
                'password_confirm': password_confirm,
                'role': role
            })
            
            response_data = response.json()

            if response.status_code == 201:
                messages.success(request, "Registration successful!")
                request.session['user_id'] = response_data['id']
                request.session['username'] = response_data['username']
                request.session['role'] = response_data['role']
                return redirect('courses')
            else:
                 messages.error(request, response_data.get('message', 'Registration failed.'))
        
        except requests.exceptions.RequestException as e:
            messages.error(request, f"Registration request failed: {e}")
            try:
                error_data = e.response.json()
                messages.error(request, f"API Error: {error_data.get('message', 'Unknown error')}")
            except (AttributeError, ValueError, TypeError):
                 messages.error(request, "An unexpected error occurred during registration.")
        except Exception as e:
            messages.error(request, f"An unexpected error occurred: {str(e)}")
            
    return render(request, 'register.html')

def chainlit_view(request):
    if not request.session.get('user_id'):
        return redirect('login')
    
    activity_id = request.GET.get('activity_id')
    
    if not activity_id:
        return redirect('courses')
        
    try:
        activity = Activity.objects.get(id=activity_id)
        user_id = request.session.get('user_id')
        
        if activity.user.id != user_id:
            pass
                
        context = {
            'activity': activity,
            'activity_id': activity_id,
            'user_id': user_id,
            'username': request.session.get('username'),
            'chainlit_url': f"http://localhost:8500/?activity_id={activity_id}&user_id={user_id}&username={urllib.parse.quote(request.session.get('username', 'User'))}&lang=en"
        }
        return render(request, 'chainlit.html', context)
    except Activity.DoesNotExist:
        messages.error(request, "Activity not found.")
        return redirect('courses')

def courses_view(request):
    if not request.session.get('user_id'):
        return redirect('login')
    
    user_id = request.session.get('user_id')
    role = request.session.get('role')
    
    if role == 'teacher':
        user = User.objects.get(id=user_id)
        courses = Course.objects.filter(owner_id=user_id).order_by('-created_at')
        
        messages.info(request, f"Logged in as teacher: {user.username}")
        
        context = {
            'courses': courses,
            'is_teacher': True,
            'enrolled_courses': courses
        }
    else:
        user = User.objects.get(id=user_id)
        courses = Course.objects.filter(enrollments__user=user).order_by('-created_at')
        context = {
            'courses': courses,
            'is_teacher': False,
            'enrolled_courses': courses
        }
    
    return render(request, 'courses.html', context) 

def create_course_view(request):
    if not request.session.get('user_id'):
        return redirect('login')
        
    user_id = request.session.get('user_id')
    
    try:
        user = User.objects.get(id=user_id)
        if user.role != 'teacher':
            messages.error(request, "Only teachers can create courses.")
            return redirect('courses')
    except User.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect('login')
    
    enrolled_courses = Course.objects.filter(owner=user).order_by('-created_at')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        
        if not title:
            messages.error(request, "Title is required.")
            return render(request, 'create_course.html', {'enrolled_courses': enrolled_courses})
            
        api_url = request.build_absolute_uri(reverse('api-1.0.0:create_course_api') + f"?user_id={user_id}")

        try:
            response = requests.post(api_url, json={
                'title': title,
                'description': description
            })
            response_data = response.json()

            if response.status_code == 201:
                messages.success(request, f"Course created successfully! Enrollment code: {response_data['enrollment_code']}")
                return redirect('courses')
            else:
                 messages.error(request, response_data.get('message', 'Course creation failed.'))

        except requests.exceptions.RequestException as e:
            messages.error(request, f"Course creation request failed: {e}")
            try:
                error_data = e.response.json()
                messages.error(request, f"API Error: {error_data.get('message', 'Unknown error')}")
            except (AttributeError, ValueError, TypeError):
                 messages.error(request, "An unexpected error occurred during course creation.")
        except Exception as e:
            messages.error(request, f"An unexpected error occurred: {str(e)}")
            
    return render(request, 'create_course.html', {'enrolled_courses': enrolled_courses})

def course_detail_view(request, course_id):
    if not request.session.get('user_id'):
        return redirect('login')
    try:
        course = Course.objects.get(id=course_id)
        user_id = request.session.get('user_id')
        user = User.objects.get(id=user_id)
    except Course.DoesNotExist:
        messages.error(request, "Course not found.")
        return redirect('courses')
        
    has_access = False
    is_teacher_of_course = False

    if course.owner_id == user_id and user.role == 'teacher':
        has_access = True
        is_teacher_of_course = True
    elif CourseEnrollment.objects.filter(user=user, course=course).exists():
        has_access = True

    if not has_access:
        messages.error(request, "You do not have permission to access this course.")
        return redirect('courses')
    
    activities = Activity.objects.filter(course=course).order_by('-created_at')
    
    participants = CourseEnrollment.objects.filter(course=course).select_related('user')
    
    if user.role == 'teacher':
        enrolled_courses = Course.objects.filter(owner=user)
    else:
        enrolled_courses = Course.objects.filter(enrollments__user=user)
    
    return render(request, 'course_detail.html', { 
        'course': course, 
        'activities': activities,
        'is_teacher': is_teacher_of_course,
        'participants': participants,
        'enrolled_courses': enrolled_courses,
        'active_course': course 
    })

def create_activity_view(request, course_id):
    if not request.session.get('user_id'):
        return redirect('login')
        
    user_id = request.session.get('user_id')

    try:
        user = User.objects.get(id=user_id)
        course = Course.objects.get(id=course_id)
        if user.role != 'teacher' or course.owner_id != user_id:
            messages.error(request, "You do not have permission to create activities in this course.")
            return redirect('course_detail', course_id=course_id) 
    except User.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect('login')
    except Course.DoesNotExist:
        messages.error(request, "Course not found.")
        return redirect('courses')
        
    if request.method == 'POST':
        activity_data = {
            "course_id": course_id,
            "title": request.POST.get('activity_title', ''),
            "description": request.POST.get('activity_description', ''),
            "expert_mode": request.POST.get('expert_mode') == 'on',
            "custom_prompt": request.POST.get('custom_prompt', '') if request.POST.get('expert_mode') == 'on' else '',
            "questions": request.POST.getlist('questions[]') or [],
            "agent_attitude": request.POST.get('agent_attitude', 'friendly'),
            "subjects": request.POST.get('subjects', ''),
            "restrict_to_subject": request.POST.get('restrict_to_subject') == 'on',
            "allow_questions": request.POST.get('allow_questions') == 'on',
            "allow_emojis": request.POST.get('allow_emojis') == 'on',
            "trust_document": request.POST.get('trust_document') == 'on'
        }
        
        api_url = request.build_absolute_uri(reverse('api-1.0.0:create_activity_api') + f"?user_id={user_id}")

        try:
            response = requests.post(api_url, json=activity_data)
            response_data = response.json()

            if response.status_code == 201:
                messages.success(request, "Activity created successfully!")
                return redirect('course_detail', course_id=course_id) # Redirect back to course detail
            else:
                messages.error(request, response_data.get('message', 'Activity creation failed.'))
        
        except requests.exceptions.RequestException as e:
            messages.error(request, f"Activity creation request failed: {e}")
            try:
                error_data = e.response.json()
                messages.error(request, f"API Error: {error_data.get('message', 'Unknown error')}")
            except (AttributeError, ValueError, TypeError):
                 messages.error(request, "An unexpected error occurred during activity creation.")
        except Exception as e:
            messages.error(request, f"An unexpected error occurred: {str(e)}")
            
        return redirect('course_detail', course_id=course_id)
    else:
        return redirect('course_detail', course_id=course_id)

def join_course_view(request):
    """View for students to join courses using enrollment codes"""
    if not request.session.get('user_id'):
        return redirect('login')
        
    user_id = request.session.get('user_id')
    user = User.objects.get(id=user_id)
    
    enrolled_courses = Course.objects.filter(enrollments__user=user).order_by('-created_at')
    
    if request.method == 'POST':
        enrollment_code = request.POST.get('enrollment_code')
        
        if not enrollment_code:
            messages.error(request, "Enrollment code is required.")
            return render(request, 'join_course.html', {'enrolled_courses': enrolled_courses}) 
            
        try:
            course = Course.objects.get(enrollment_code=enrollment_code)
            
            if CourseEnrollment.objects.filter(user=user, course=course).exists():
                messages.warning(request, f"You are already enrolled in the course '{course.title}'.")
            else:
                CourseEnrollment.objects.create(
                    user=user,
                    course=course
                )
                
                messages.success(request, f"Successfully enrolled in course '{course.title}'!")
            
            return redirect('activities')
            
        except Course.DoesNotExist:
            messages.error(request, "Invalid enrollment code.")
            return render(request, 'join_course.html', {'enrolled_courses': enrolled_courses}) 
            
    return render(request, 'join_course.html', {'enrolled_courses': enrolled_courses})

def dashboard_view(request):
    if not request.session.get('user_id'):
        return redirect('login')
    user_id = request.session.get('user_id')
    user = User.objects.get(id=user_id)
    if user.role != 'teacher':
        messages.error(request, "Only teachers can access the dashboard.")
        return redirect('courses')

    courses = Course.objects.filter(owner=user).order_by('-created_at')
    selected_course_id = request.GET.get('course_id')
    if selected_course_id:
        selected_course = courses.filter(id=selected_course_id).first()
    else:
        selected_course = courses.first()
    if not selected_course:
        messages.info(request, "No courses found. Create one first.")
        return redirect('create_course')

    students = CourseEnrollment.objects.filter(course=selected_course).select_related('user')
    activities_count = Activity.objects.filter(course=selected_course).count()
    student_messages_qs = Message.objects.filter(
        thread__activity__course=selected_course,
        role='student'
    ).select_related('thread__user')
    total_messages = student_messages_qs.count()

    counts = {}
    lengths = {}
    for msg in student_messages_qs:
        username = msg.thread.user.username
        counts[username] = counts.get(username, 0) + 1
        lengths[username] = lengths.get(username, 0) + len(msg.content)
    
    stats_per_student = []
    for username, count in counts.items():
        avg_len = lengths[username] / count if count else 0
        stats_per_student.append({
            'username': username,
            'message_count': count,
            'avg_length': round(avg_len, 2)
        })

    last_messages = student_messages_qs.order_by('-timestamp')[:10]

    context = {
        'courses': courses,
        'selected_course': selected_course,
        'students_count': students.count(),
        'activities_count': activities_count,
        'total_messages': total_messages,
        'stats_per_student': stats_per_student,
        'last_messages': last_messages,
        'enrolled_courses': courses  
    }
    return render(request, 'dashboard.html', context)
    
def edit_course_view(request, course_id):
    """View for teachers to edit their courses"""
    if not request.session.get('user_id'):
        return redirect('login')
        
    user_id = request.session.get('user_id')
    user = User.objects.get(id=user_id)
    
    if user.role != 'teacher':
        messages.error(request, "Only teachers can edit courses.")
        return redirect('courses')
    
    enrolled_courses = Course.objects.filter(owner=user).order_by('-created_at')
    
    try:
        course = Course.objects.get(id=course_id)
        
        if course.owner.id != user_id:
            messages.error(request, "You can only edit your own courses.")
            return redirect('courses')
            
        if request.method == 'POST':
            title = request.POST.get('title')
            description = request.POST.get('description')
            
            if not title:
                messages.error(request, "Title is required.")
                return render(request, 'create_course.html', {
                    'course': course, 
                    'edit_mode': True,
                    'enrolled_courses': enrolled_courses
                })
                
            course.title = title
            course.description = description
            course.save()
            
            messages.success(request, "Course updated successfully!")
            return redirect('course_detail', course_id=course.id)
            
        return render(request, 'create_course.html', {
            'course': course, 
            'edit_mode': True,
            'enrolled_courses': enrolled_courses
        })
        
    except Course.DoesNotExist:
        messages.error(request, "Course not found.")
        return redirect('courses')

def activities_view(request):
    """View for displaying all activities"""
    if not request.session.get('user_id'):
        return redirect('login')
    
    user_id = request.session.get('user_id')
    role = request.session.get('role')
    user = User.objects.get(id=user_id)
    
    if role == 'teacher':
        teacher_courses = Course.objects.filter(owner_id=user_id)
        activities = Activity.objects.filter(course__in=teacher_courses).order_by('-created_at')
        context = {
            'activities': activities,
            'is_teacher': True,
            'courses': teacher_courses,
            'enrolled_courses': teacher_courses
        }
    else:
        enrolled_courses = Course.objects.filter(enrollments__user=user)
        activities = Activity.objects.filter(course__in=enrolled_courses).order_by('-created_at')
        context = {
            'activities': activities,
            'is_teacher': False,
            'courses': enrolled_courses,
            'enrolled_courses': enrolled_courses
        }
    
    return render(request, 'activities.html', context)

def profile_view(request):
    if not request.session.get('user_id'):
        return redirect('login')
        
    user_id = request.session.get('user_id')
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect('login')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        new_password_confirm = request.POST.get('new_password_confirm')
        
        if not current_password:
            messages.error(request, "Current password is required to make changes.")
            return render(request, 'profile.html', {'user': user})
            
        profile_data = {
            'username': username,
            'email': email,
            'current_password': current_password
        }
        
        if new_password:
            profile_data['new_password'] = new_password
            profile_data['new_password_confirm'] = new_password_confirm
            
        api_url = request.build_absolute_uri(reverse('api-1.0.0:update_user_profile', args=[user_id]))
        
        try:
            response = requests.put(api_url, json=profile_data)
            
            if response.status_code == 200:
                user_data = response.json()
                request.session['username'] = user_data['username']
                messages.success(request, "Profile updated successfully!")
                return redirect('profile')
            else:
                error_data = response.json()
                messages.error(request, error_data.get('message', 'Profile update failed.'))
                
        except requests.exceptions.RequestException as e:
            messages.error(request, f"Profile update request failed: {e}")
            try:
                error_data = e.response.json()
                messages.error(request, f"API Error: {error_data.get('message', 'Unknown error')}")
            except (AttributeError, ValueError, TypeError):
                messages.error(request, "An unexpected error occurred during profile update.")
        except Exception as e:
            messages.error(request, f"An unexpected error occurred: {str(e)}")
    
    if user.role == 'teacher':
        enrolled_courses = Course.objects.filter(owner=user)
    else:
        enrolled_courses = Course.objects.filter(enrollments__user=user)
    
    return render(request, 'profile.html', {
        'user': user,
        'enrolled_courses': enrolled_courses
    })
