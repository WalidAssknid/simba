from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
import urllib
import requests
from django.urls import reverse
from django.conf import settings
from .models import User, Course, Activity, CourseEnrollment, Message
import json

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
    selected_activity_id = request.GET.get('activity_id')
    
    active_tab = request.GET.get('active_tab', 'conversation-stats')
    if active_tab == 'student-clusters':
        active_tab = 'student-engagement'
    
    authoritative_id_for_logic_and_template = None  
    course_object_for_context = None                

    if not courses.exists():
        messages.info(request, "No courses found. Create one first.")
        return redirect('create_course')

    if selected_course_id and selected_course_id != 'all': 
        try:
            course_id_as_int = int(selected_course_id)
            _fetched_course_obj = courses.filter(id=course_id_as_int).first()
            if _fetched_course_obj:
                course_object_for_context = _fetched_course_obj
                authoritative_id_for_logic_and_template = _fetched_course_obj.id 
            else:
                messages.warning(request, f"Course ID '{selected_course_id}' not found or not accessible for your account. Defaulting to all courses.")
                course_object_for_context = courses.first() 
        except ValueError:
            messages.warning(request, f"Invalid course ID format: '{selected_course_id}'. Defaulting to all courses.")
            course_object_for_context = courses.first() 
    else:
        course_object_for_context = courses.first() 

    selected_course_id = authoritative_id_for_logic_and_template
    selected_course = course_object_for_context

    if selected_course_id is None: 
        activities = Activity.objects.filter(course__in=courses).order_by('-created_at')
        
        students = CourseEnrollment.objects.filter(course__in=courses).select_related('user', 'course')
        
        student_dict = {}
        for enrollment in students:
            if enrollment.user.id not in student_dict:
                student_dict[enrollment.user.id] = {
                    'id': enrollment.user.id,
                    'username': enrollment.user.username,
                    'courses': [enrollment.course.title]
                }
            else:
                student_dict[enrollment.user.id]['courses'].append(enrollment.course.title)
        
        all_students = [
            {'id': s['id'], 
             'username': f"{s['username']} ({', '.join(s['courses'][:2])}{' + more' if len(s['courses']) > 2 else ''})"
            } for s in student_dict.values()
        ]
        
        base_msg_query = Message.objects.filter(
            thread__activity__course__in=courses
        ).select_related('thread__user', 'thread__activity')
    else:
        activities = Activity.objects.filter(course=selected_course).order_by('-created_at')
        
        students = CourseEnrollment.objects.filter(course=selected_course).select_related('user')
        all_students = [{'id': s.user.id, 'username': s.user.username} for s in students]
        
        base_msg_query = Message.objects.filter(
            thread__activity__course=selected_course
        ).select_related('thread__user', 'thread__activity')
    
    selected_activity = None
    if selected_activity_id and selected_activity_id != 'all':
        selected_activity = activities.filter(id=selected_activity_id).first()
    
    student_messages_qs = base_msg_query.filter(role='user')
    
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

    if total_messages > 0:
        avg_message_length = sum(lengths.values()) / total_messages
    else:
        avg_message_length = 0
    
    activity_stats = {}
    for activity in activities:
        activity_msgs = Message.objects.filter(
            thread__activity=activity,
            role='user'
        )
        msg_count = activity_msgs.count()
        
        if msg_count > 0:
            total_length = sum([len(msg.content) for msg in activity_msgs])
            avg_length = total_length / msg_count
        else:
            avg_length = 0
            
        activity_stats[activity.id] = {
            'name': activity.title or f"Activity {activity.id}",
            'message_count': msg_count,
            'avg_length': round(avg_length, 2)
        }
    
    activity_names = [stats['name'] for activity_id, stats in activity_stats.items()]
    activity_message_counts = [stats['message_count'] for activity_id, stats in activity_stats.items()]
    activity_avg_lengths = [stats['avg_length'] for activity_id, stats in activity_stats.items()]
    
    if counts:
        avg_count = sum(counts.values()) / len(counts)
        avg_length = sum(lengths.values()) / len(lengths)
    else:
        avg_count = 0
        avg_length = 0
    
    segment_many_long = []
    segment_few_long = []
    segment_many_short = []
    segment_few_short = []
    
    for username, count in counts.items():
        length = lengths[username]
        point = {'x': length, 'y': count}
        
        if count > avg_count and length > avg_length:
            segment_many_long.append(point)
        elif count <= avg_count and length > avg_length:
            segment_few_long.append(point)
        elif count > avg_count and length <= avg_length:
            segment_many_short.append(point)
        else:
            segment_few_short.append(point)
    
    avg_time_seconds = 0
    student_duration_data = {}
    
    for thread in student_messages_qs.values('thread').distinct():
        thread_messages = Message.objects.filter(thread_id=thread['thread']).order_by('timestamp')
        if thread_messages.count() > 1:
            first_msg = thread_messages.first()
            last_msg = thread_messages.last()
            if first_msg and last_msg:
                duration = (last_msg.timestamp - first_msg.timestamp).total_seconds()
                student_id = first_msg.thread.user_id
                student_duration_data[student_id] = student_duration_data.get(student_id, 0) + duration
    
    if student_duration_data:
        avg_time_seconds = sum(student_duration_data.values()) / len(student_duration_data)
        
    hours = int(avg_time_seconds // 3600)
    minutes = int((avg_time_seconds % 3600) // 60)
    avg_time_per_student = f"{hours}h {minutes}m"
    
    raw_messages = base_msg_query.order_by('-timestamp')[:100]
    
    context = {
        'courses': courses,
        'selected_course': selected_course,
        'selected_course_id': selected_course_id,
        'selected_activity': selected_activity,
        'activities': activities,
        'students_count': students.count(),
        'activities_count': activities.count(),
        'total_messages': total_messages,
        'avg_message_length': round(avg_message_length, 2),
        'avg_time_per_student': avg_time_per_student,
        'stats_per_student': stats_per_student,
        'all_students': all_students,
        'raw_messages': raw_messages,
        'enrolled_courses': courses,
        'activity_names': activity_names,
        'activity_message_counts': activity_message_counts,
        'activity_avg_lengths': activity_avg_lengths,
        'segment_many_long': segment_many_long,
        'segment_few_long': segment_few_long,
        'segment_many_short': segment_many_short,
        'segment_few_short': segment_few_short,
        'active_tab': active_tab
    }
    
    context['activity_names_json'] = json.dumps(activity_names)
    context['activity_message_counts_json'] = json.dumps(activity_message_counts)
    context['activity_avg_lengths_json'] = json.dumps(activity_avg_lengths)
    context['segment_many_long_json'] = json.dumps(segment_many_long)
    context['segment_few_long_json'] = json.dumps(segment_few_long)
    context['segment_many_short_json'] = json.dumps(segment_many_short)
    context['segment_few_short_json'] = json.dumps(segment_few_short)
    
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