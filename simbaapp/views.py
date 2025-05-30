from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
import urllib
import requests
from django.urls import reverse
from django.conf import settings
from .models import User, Course, Activity, CourseEnrollment, Message
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def home_view(request):
    if request.session.get('user_id'):
        return redirect('courses')
    return render(request, 'home.html')

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
        
        api_url = request.build_absolute_uri(reverse('api-1.0.0:register_user'))
        
        try:
            response = requests.post(api_url, json={
                'username': username,
                'email': email,
                'password': password,
                'password_confirm': password_confirm
            })
            
            response_data = response.json()

            if response.status_code == 201:
                messages.success(request, "Registration successful!")
                request.session['user_id'] = response_data['id']
                request.session['username'] = response_data['username']
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
    logger.info(f"Asked for the chainlit view")
    if not request.session.get('user_id'):
        return redirect('login')
    
    activity_id = request.GET.get('activity_id')
    thread_id = request.GET.get('thread_id') 
    
    if not activity_id:
        return redirect('courses')
        
    try:
        print(f"chainlit_view called with activity_id={activity_id}, thread_id={thread_id}", flush=True)
        activity = Activity.objects.get(id=activity_id)
        user_id = request.session.get('user_id')
        username = request.session.get('username', 'User')
        
        # Create Chainlit session via new API
        api_url = request.build_absolute_uri('/api/chainlit/create-session')
        session_payload = {
            'activity_id': int(activity_id),
            'user_id': user_id,
            'username': username
        }
        
        if thread_id:
            session_payload['thread_id'] = int(thread_id)
        
        try:
            response = requests.post(api_url, json=session_payload)
            response.raise_for_status()
            session_data = response.json()
            
            # Chainlit URL without any parameters
            chainlit_base_url = f"https://simba-refact.irit.fr/chainlit"
            chainlit_url = chainlit_base_url 
            
            context = {
                'activity': activity,
                'activity_id': activity_id,
                'user_id': user_id,
                'username': username,
                'chainlit_url': chainlit_url,
                'thread_id': session_data['thread_id'],
                'session_id': session_data['session_id'],
                'session_data': session_data
            }
            return render(request, 'chainlit.html', context)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create Chainlit session: {e}")
            # Error - redirect to courses instead of fallback
            messages.error(request, "Failed to start chat session. Please try again.")
            return redirect('courses')
            
    except Activity.DoesNotExist:
        messages.error(request, "Activity not found.")
        return redirect('courses')

def courses_view(request):
    if not request.session.get('user_id'):
        return redirect('login')
    
    user_id = request.session.get('user_id')
    user = User.objects.get(id=user_id)
    
    # Get courses where user is owner (teacher)
    owned_courses = Course.objects.filter(owner_id=user_id).order_by('-created_at')
    
    # Get courses where user is enrolled (student or teacher)
    enrolled_courses = Course.objects.filter(enrollments__user=user).order_by('-created_at')
    
    # Combine all courses (owned + enrolled)
    all_courses = (owned_courses | enrolled_courses).distinct().order_by('-created_at')
    
    # Add role information to each course
    courses_with_roles = []
    for course in all_courses:
        course_info = {
            'course': course,
            'is_owner': course.owner_id == user_id,
            'enrollment_role': None
        }
        
        # Check if user has an enrollment record for this course
        enrollment = CourseEnrollment.objects.filter(user=user, course=course).first()
        if enrollment:
            course_info['enrollment_role'] = enrollment.role
            
        courses_with_roles.append(course_info)
    
    context = {
        'courses_with_roles': courses_with_roles,
        'user': user,
        'can_create_course': user.can_create_course(),
        'can_join_course': user.can_join_course(),
        'owned_courses_count': user.get_owned_courses_count(),
        'enrolled_courses_count': user.get_enrolled_courses_count(),
        'total_activities_count': user.get_total_activities_count()
    }
    
    return render(request, 'courses.html', context) 

def create_course_view(request):
    if not request.session.get('user_id'):
        return redirect('login')
        
    user_id = request.session.get('user_id')
    
    try:
        user = User.objects.get(id=user_id)
        if not user.can_create_course():
            messages.error(request, f"You can only create up to 3 courses. You currently have {user.get_owned_courses_count()} courses.")
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
    logger.info(f"requested course {course_id}")

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
    is_owner = course.owner_id == user_id
    user_role_in_course = None

    # Check if user is owner
    if is_owner:
        has_access = True
        user_role_in_course = 'owner'
    else:
        # Check if user is enrolled
        enrollment = CourseEnrollment.objects.filter(user=user, course=course).first()
        if enrollment:
            has_access = True
            user_role_in_course = enrollment.role

    if not has_access:
        messages.error(request, "You do not have permission to access this course.")
        return redirect('courses')
    
    # Show all activities if user is owner or teacher, only visible if student
    if is_owner or user_role_in_course == 'teacher':
        activities = Activity.objects.filter(course=course).order_by('-created_at')
    else:
        activities = Activity.objects.filter(course=course, is_visible=True).order_by('-created_at')
    
    participants = CourseEnrollment.objects.filter(course=course).select_related('user')
    
    # Get all courses for navigation
    owned_courses = Course.objects.filter(owner=user)
    enrolled_courses = Course.objects.filter(enrollments__user=user)
    all_courses = (owned_courses | enrolled_courses).distinct()
    
    return render(request, 'course_detail.html', { 
        'course': course, 
        'activities': activities,
        'is_owner': is_owner,
        'user_role_in_course': user_role_in_course,
        'participants': participants,
        'enrolled_courses': all_courses,
        'active_course': course 
    })

def create_activity_view(request, course_id):
    if not request.session.get('user_id'):
        return redirect('login')
        
    user_id = request.session.get('user_id')

    try:
        user = User.objects.get(id=user_id)
        course = Course.objects.get(id=course_id)
        
        # Check if user can create activities (limit check)
        if not user.can_create_activity(course):
            total_activities = Activity.objects.filter(owner=user).count()
            messages.error(request, f"You can only create up to 6 activities total. You currently have {total_activities} activities.")
            return redirect('course_detail', course_id=course_id)
        
        # Check if user has permission to create activities in this course
        is_owner = course.owner_id == user_id
        enrollment = CourseEnrollment.objects.filter(user=user, course=course).first()
        can_create = is_owner or (enrollment and enrollment.role == 'teacher')
        
        if not can_create:
            messages.error(request, "You do not have permission to create activities in this course.")
            return redirect('course_detail', course_id=course_id) 
    except User.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect('login')
    except Course.DoesNotExist:
        messages.error(request, "Course not found.")
        return redirect('courses')
        
    if request.method == 'POST':
        from datetime import datetime
        
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        start_date_obj = None
        end_date_obj = None
        
        if start_date:
            try:
                start_date_obj = datetime.fromisoformat(start_date)
            except ValueError:
                messages.error(request, "Invalid start date format.")
                return redirect('course_detail', course_id=course_id)
        
        if end_date:
            try:
                end_date_obj = datetime.fromisoformat(end_date)
            except ValueError:
                messages.error(request, "Invalid end date format.")
                return redirect('course_detail', course_id=course_id)
        
        # Process questions from JSON
        questions_json = request.POST.get('questions[]', '[]')
        try:
            questions = json.loads(questions_json) if questions_json else []
        except json.JSONDecodeError:
            questions = []
        
        # Process files from JSON
        files_json = request.POST.get('files[]', '[]')
        try:
            files_data = json.loads(files_json) if files_json else []
        except json.JSONDecodeError:
            files_data = []

        activity_data = {
            "course_id": course_id,
            "title": request.POST.get('activity_title', ''),
            "description": request.POST.get('activity_description', ''),
            "expert_mode": request.POST.get('expert_mode') == 'on',
            "custom_prompt": request.POST.get('custom_prompt', '') if request.POST.get('expert_mode') == 'on' else '',
            "questions": questions,
            "agent_attitude": request.POST.get('agent_attitude', 'friendly'),
            "subjects": request.POST.get('subjects', ''),
            "restrict_to_subject": request.POST.get('restrict_to_subject') == 'on',
            "allow_questions": request.POST.get('allow_questions') == 'on',
            "allow_emojis": request.POST.get('allow_emojis') == 'on',
            "trust_document": request.POST.get('trust_document') == 'on',
            "word_limit": int(request.POST.get('word_limit', 0)) or 0,
            "start_date": start_date_obj.isoformat() if start_date_obj else None,
            "end_date": end_date_obj.isoformat() if end_date_obj else None,
            "is_visible": request.POST.get('is_visible') == 'on',
            "allow_redo": request.POST.get('allow_redo') == 'on',
            "files": files_data
        }
        
        api_url = request.build_absolute_uri(reverse('api-1.0.0:create_activity_api') + f"?user_id={user_id}")

        try:
            response = requests.post(api_url, json=activity_data)
            response_data = response.json()

            if response.status_code == 201:
                messages.success(request, "Activity created successfully!")
                return redirect('course_detail', course_id=course_id)
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
    """View for users to join courses using enrollment codes"""
    if not request.session.get('user_id'):
        return redirect('login')
        
    user_id = request.session.get('user_id')
    user = User.objects.get(id=user_id)
    
    # Get all courses for navigation
    owned_courses = Course.objects.filter(owner=user)
    enrolled_courses = Course.objects.filter(enrollments__user=user)
    all_courses = (owned_courses | enrolled_courses).distinct().order_by('-created_at')
    
    if request.method == 'POST':
        enrollment_code = request.POST.get('enrollment_code')
        role = request.POST.get('role', 'student')  # Default to student
        
        if not enrollment_code:
            messages.error(request, "Enrollment code is required.")
            return render(request, 'join_course.html', {'enrolled_courses': all_courses}) 
        
        # Check if user can join more courses
        if not user.can_join_course():
            total_courses = user.get_owned_courses_count() + user.get_enrolled_courses_count()
            messages.error(request, f"You can only be in up to 3 courses total. You are currently in {total_courses} courses.")
            return render(request, 'join_course.html', {'enrolled_courses': all_courses})
            
        try:
            course = Course.objects.get(enrollment_code=enrollment_code)
            
            # Check if user is already the owner
            if course.owner_id == user_id:
                messages.warning(request, f"You are already the owner of the course '{course.title}'.")
                return redirect('course_detail', course_id=course.id)
            
            # Check if user is already enrolled
            if CourseEnrollment.objects.filter(user=user, course=course).exists():
                messages.warning(request, f"You are already enrolled in the course '{course.title}'.")
                return redirect('course_detail', course_id=course.id)
            else:
                CourseEnrollment.objects.create(
                    user=user,
                    course=course,
                    role=role
                )
                
                messages.success(request, f"Successfully enrolled in course '{course.title}' as {role}!")
            
            return redirect('course_detail', course_id=course.id)
            
        except Course.DoesNotExist:
            messages.error(request, "Invalid enrollment code.")
            return render(request, 'join_course.html', {'enrolled_courses': all_courses}) 
            
    return render(request, 'join_course.html', {'enrolled_courses': all_courses})

def dashboard_view(request):
    logger.info(f"Dashboard view called - Session keys: {list(request.session.keys())}")
    logger.info(f"Session user_id: {request.session.get('user_id')}")
    logger.info(f"Session age: {request.session.get_expiry_age()}")
    
    if not request.session.get('user_id'):
        logger.warning("No user_id in session, redirecting to login")
        return redirect('login')
    user_id = request.session.get('user_id')
    
    try:
        user = User.objects.get(id=user_id)
        logger.info(f"User found: {user.username}")
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} not found")
        request.session.flush()
        return redirect('login')
    
    # Debug logging
    logger.info(f"Dashboard view called for user {user_id}, GET params: {request.GET}")
    
    # Check what roles the user has
    # 1. Courses where user is the owner (creator) - automatically has teacher privileges + owner privileges
    owned_courses = Course.objects.filter(owner=user)
    
    # 2. Courses where user is enrolled as teacher (not owner)
    teacher_enrollments = CourseEnrollment.objects.filter(user=user, role='teacher')
    teacher_courses = Course.objects.filter(enrollments__in=teacher_enrollments)
    
    # 3. All courses where user has teacher privileges (owner OR enrolled as teacher)
    all_teacher_courses = (owned_courses | teacher_courses).distinct()
    
    # 4. Courses where user is enrolled as student
    student_enrollments = CourseEnrollment.objects.filter(user=user, role='student')
    student_courses = Course.objects.filter(enrollments__in=student_enrollments)
    
    # Determine available roles for the user
    has_teacher_role = all_teacher_courses.exists()  # Owner OR teacher enrollment
    has_student_role = student_courses.exists()      # Student enrollment
    has_owner_role = owned_courses.exists()          # Course owner (subset of teacher role)
    
    logger.info(f"User roles - owned_courses: {owned_courses.count()}, teacher_enrollments: {teacher_enrollments.count()}, student_enrollments: {student_enrollments.count()}")
    logger.info(f"User roles - has_teacher_role: {has_teacher_role}, has_student_role: {has_student_role}, has_owner_role: {has_owner_role}")
    
    # Determine default view_as based on available roles
    view_as = request.GET.get('view_as')
    logger.info(f"Requested view_as: {view_as}")
    
    # Validate view_as request
    if view_as:
        if view_as == 'teacher':
            if not has_teacher_role:
                messages.warning(request, "You don't have teacher privileges in any courses. You need to own a course or be enrolled as a teacher.")
                view_as = 'student' if has_student_role else 'teacher'  # Fallback
        elif view_as == 'student':
            if not has_student_role:
                messages.warning(request, "You are not enrolled as a student in any courses. Join a course as a student to access this view.")
                view_as = 'teacher' if has_teacher_role else 'student'  # Fallback
    
    if not view_as:
        # Auto-detect: prefer teacher if available, otherwise student
        if has_teacher_role:
            view_as = 'teacher'
        elif has_student_role:
            view_as = 'student'
        else:
            # User has no courses at all, default to teacher view
            view_as = 'teacher'
    
    logger.info(f"Final view_as: {view_as}")
    
    # Handle view selection - show appropriate courses based on validated view
    if view_as == 'teacher':
        if not has_teacher_role:
            messages.info(request, "You don't have any courses yet. Create a course or join one as a teacher to access analytics features.")
            courses = Course.objects.none()  # Empty queryset
        else:
            courses = all_teacher_courses.order_by('-created_at')
    else:  # view_as == 'student'
        if not has_student_role:
            messages.info(request, "You are not enrolled in any courses as a student yet. Join a course to view your statistics.")
            courses = Course.objects.none()  # Empty queryset
        else:
            courses = student_courses.order_by('-created_at')
    
    logger.info(f"Courses count: {courses.count()}")
    
    selected_course_id = request.GET.get('course_id')
    selected_activity_id = request.GET.get('activity_id')
    
    # Debug logging for course selection
    logger.info(f"Requested course_id: {selected_course_id}")
    logger.info(f"Available courses: {[c.id for c in courses]}")
    logger.info(f"Available course titles: {[c.title for c in courses]}")
    
    # Set default tab based on view_as
    if view_as == 'student':
        # Force student-stats tab for student view
        active_tab = 'student-stats'
    else:
        active_tab = request.GET.get('active_tab', 'conversation-stats')
    
    logger.info(f"Active tab: {active_tab}")
    
    if active_tab == 'student-clusters':
        active_tab = 'student-engagement'
    
    authoritative_id_for_logic_and_template = None  
    course_object_for_context = None                

    if selected_course_id and selected_course_id != 'all': 
        try:
            course_id_as_int = int(selected_course_id)
            _fetched_course_obj = courses.filter(id=course_id_as_int).first()
            logger.info(f"Looking for course ID {course_id_as_int} in available courses")
            if _fetched_course_obj:
                course_object_for_context = _fetched_course_obj
                authoritative_id_for_logic_and_template = _fetched_course_obj.id 
                logger.info(f"Found course: {_fetched_course_obj.title}")
            else:
                logger.warning(f"Course ID {course_id_as_int} not found in available courses for view_as={view_as}")
                
                # Check if course exists in any context (more user-friendly message)
                course_exists_somewhere = Course.objects.filter(id=course_id_as_int).exists()
                if course_exists_somewhere:
                    messages.info(request, f"The selected course is not available in {view_as} view. Showing all available courses instead.")
                else:
                    messages.warning(request, f"Course ID '{selected_course_id}' does not exist. Showing all available courses instead.")
                
                course_object_for_context = courses.first() 
        except ValueError:
            logger.error(f"Invalid course ID format: {selected_course_id}")
            messages.warning(request, f"Invalid course ID format: '{selected_course_id}'. Defaulting to all courses.")
            course_object_for_context = courses.first() 
    else:
        course_object_for_context = courses.first()

    selected_course_id = authoritative_id_for_logic_and_template
    selected_course = course_object_for_context
    
    logger.info(f"Final selected_course_id: {selected_course_id}")
    logger.info(f"Final selected_course: {selected_course.title if selected_course else 'None'}")

    # Handle empty courses case
    if not courses.exists():
        logger.warning(f"No courses available for user {user_id} in {view_as} view")
        # Return empty dashboard with message
        context = {
            'courses': courses,
            'selected_course': None,
            'selected_course_id': None,
            'selected_activity': None,
            'activities': Activity.objects.none(),
            'students_count': 0,
            'activities_count': 0,
            'total_messages': 0,
            'avg_message_length': 0,
            'avg_time_per_student': "0h 0m",
            'stats_per_student': [],
            'all_students': [],
            'raw_messages': [],
            'enrolled_courses': courses,
            'activity_names': [],
            'activity_message_counts': [],
            'activity_avg_lengths': [],
            'segment_many_long': [],
            'segment_few_long': [],
            'segment_many_short': [],
            'segment_few_short': [],
            'active_tab': active_tab,
            'view_as': view_as,
            'user': user,
            'student_personal_stats': None,
            'has_teacher_role': has_teacher_role,
            'has_student_role': has_student_role,
            'has_owner_role': has_owner_role,
            'owned_courses_count': owned_courses.count(),
            'teacher_enrollments_count': teacher_enrollments.count(),
            'student_enrollments_count': student_enrollments.count(),
            'is_course_owner': owned_courses.exists(),
            'is_enrolled_teacher': teacher_enrollments.exists(),
            'is_enrolled_student': student_enrollments.exists(),
        }
        
        # Add JSON context for empty state
        context['activity_names_json'] = json.dumps([])
        context['activity_message_counts_json'] = json.dumps([])
        context['activity_avg_lengths_json'] = json.dumps([])
        context['segment_many_long_json'] = json.dumps([])
        context['segment_few_long_json'] = json.dumps([])
        context['segment_many_short_json'] = json.dumps([])
        context['segment_few_short_json'] = json.dumps([])
        
        return render(request, 'dashboard.html', context)

    if selected_course_id is None: 
        # Show all courses - no specific course selected
        activities = Activity.objects.filter(course__in=courses).order_by('-created_at')
        
        # For teacher views, show all enrollments in their courses
        # For student view, show only student enrollments in courses where user is student
        if view_as == 'student':
            students = CourseEnrollment.objects.filter(
                course__in=courses,
                role='student'
            ).select_related('user', 'course')
        else:
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
        # Specific course selected
        activities = Activity.objects.filter(course=selected_course).order_by('-created_at')
        
        # For teacher views, show all enrollments in the selected course
        # For student view, show only student enrollments
        if view_as == 'student':
            students = CourseEnrollment.objects.filter(
                course=selected_course,
                role='student'
            ).select_related('user')
        else:
            students = CourseEnrollment.objects.filter(course=selected_course).select_related('user')
            
        all_students = [{'id': s.user.id, 'username': s.user.username} for s in students]
        
        base_msg_query = Message.objects.filter(
            thread__activity__course=selected_course
        ).select_related('thread__user', 'thread__activity')
    
    selected_activity = None
    if selected_activity_id and selected_activity_id != 'all':
        selected_activity = activities.filter(id=selected_activity_id).first()
    
    # Filter messages based on view_as
    if view_as == 'student':
        # For student view, only show the current user's messages (their own data)
        student_messages_qs = base_msg_query.filter(
            role='user',
            thread__user=user
        )
    else:
        # For teacher views, show all user messages from students
        student_user_ids = CourseEnrollment.objects.filter(
            course__in=courses,
            role='student'
        ).values_list('user_id', flat=True)
        student_messages_qs = base_msg_query.filter(
            role='user',
            thread__user_id__in=student_user_ids
        )
    
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
        if view_as == 'student':
            # For student view, only count messages from the current user
            activity_msgs = Message.objects.filter(
                thread__activity=activity,
                role='user',
                thread__user=user
            )
        else:
            # For teacher views, count messages from all students
            student_user_ids = CourseEnrollment.objects.filter(
                course__in=courses,
                role='student'
            ).values_list('user_id', flat=True)
            activity_msgs = Message.objects.filter(
                thread__activity=activity,
                role='user',
                thread__user_id__in=student_user_ids
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
    
    # Filter raw messages based on view_as
    if view_as == 'student':
        # Show only the current user's messages when in student view
        raw_messages = base_msg_query.filter(thread__user=user).order_by('-timestamp')[:100]
    else:
        # Show all messages for teachers
        raw_messages = base_msg_query.order_by('-timestamp')[:100]
    
    # If viewing as student, prepare personal statistics
    student_personal_stats = None
    if view_as == 'student':
        # Get personal messages for the current user in courses where they are students
        personal_messages = base_msg_query.filter(thread__user=user, role='user')
        personal_message_count = personal_messages.count()
        
        if personal_message_count > 0:
            total_chars = sum([len(msg.content) for msg in personal_messages])
            avg_length = total_chars / personal_message_count
            
            # Get activities the user participated in as a student
            participated_activities = Activity.objects.filter(
                threads__user=user,
                course__in=courses
            ).distinct().count()
            
            # Get retry count (threads with attempt_number > 1)
            from simbaapp.models import Thread
            retry_count = Thread.objects.filter(
                user=user,
                activity__course__in=courses,
                attempt_number__gt=1
            ).count()
            
            student_personal_stats = {
                'activities_count': participated_activities,
                'messages_count': personal_message_count,
                'total_chars': total_chars,
                'avg_length': round(avg_length, 2),
                'retries_count': retry_count
            }
        else:
            student_personal_stats = {
                'activities_count': 0,
                'messages_count': 0,
                'total_chars': 0,
                'avg_length': 0,
                'retries_count': 0
            }
    
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
        'active_tab': active_tab,
        'view_as': view_as,
        'user': user,
        'student_personal_stats': student_personal_stats,
        'has_teacher_role': has_teacher_role,
        'has_student_role': has_student_role,
        'has_owner_role': has_owner_role,
        # Additional role details for better understanding
        'owned_courses_count': owned_courses.count(),
        'teacher_enrollments_count': teacher_enrollments.count(),
        'student_enrollments_count': student_enrollments.count(),
        'is_course_owner': owned_courses.exists(),
        'is_enrolled_teacher': teacher_enrollments.exists(),
        'is_enrolled_student': student_enrollments.exists(),
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
    """View for course owners to edit their courses"""
    if not request.session.get('user_id'):
        return redirect('login')
        
    user_id = request.session.get('user_id')
    user = User.objects.get(id=user_id)
    
    # Get all courses for navigation
    owned_courses = Course.objects.filter(owner=user)
    enrolled_courses = Course.objects.filter(enrollments__user=user)
    all_courses = (owned_courses | enrolled_courses).distinct().order_by('-created_at')
    
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
                    'enrolled_courses': all_courses
                })
                
            course.title = title
            course.description = description
            course.save()
            
            messages.success(request, "Course updated successfully!")
            return redirect('course_detail', course_id=course.id)
            
        return render(request, 'create_course.html', {
            'course': course, 
            'edit_mode': True,
            'enrolled_courses': all_courses
        })
        
    except Course.DoesNotExist:
        messages.error(request, "Course not found.")
        return redirect('courses')

def activities_view(request):
    """View for displaying all activities"""
    if not request.session.get('user_id'):
        return redirect('login')
    
    user_id = request.session.get('user_id')
    user = User.objects.get(id=user_id)
    
    # Get all courses user has access to
    owned_courses = Course.objects.filter(owner_id=user_id)
    enrolled_courses = Course.objects.filter(enrollments__user=user)
    all_courses = (owned_courses | enrolled_courses).distinct()
    
    # Get activities with role information
    activities_with_roles = []
    
    for course in all_courses:
        is_owner = course.owner_id == user_id
        enrollment = CourseEnrollment.objects.filter(user=user, course=course).first()
        user_role = 'owner' if is_owner else (enrollment.role if enrollment else None)
        
        # Get activities based on role
        if is_owner or (enrollment and enrollment.role == 'teacher'):
            # Show all activities for owners and teachers
            course_activities = Activity.objects.filter(course=course).order_by('-created_at')
        else:
            # Show only visible activities for students
            course_activities = Activity.objects.filter(course=course, is_visible=True).order_by('-created_at')
        
        for activity in course_activities:
            activities_with_roles.append({
                'activity': activity,
                'course': course,
                'user_role': user_role,
                'is_owner': is_owner
            })
    
    # Sort by creation date
    activities_with_roles.sort(key=lambda x: x['activity'].created_at, reverse=True)
    
    # Check if user can create activities (has at least one course with space)
    can_create_activity = user.can_create_activity()
    
    context = {
        'activities_with_roles': activities_with_roles,
        'courses': all_courses,
        'enrolled_courses': all_courses,
        'user': user,
        'can_create_activity': can_create_activity
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
    
    # Get all courses for navigation
    owned_courses = Course.objects.filter(owner=user)
    enrolled_courses = Course.objects.filter(enrollments__user=user)
    all_courses = (owned_courses | enrolled_courses).distinct()
    
    return render(request, 'profile.html', {
        'user': user,
        'enrolled_courses': all_courses
    })