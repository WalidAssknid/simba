# filepath: /Users/lenonanthony/Documents/simba-2025/simbaapp/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
import urllib
from .models import User, Course, Activity, CourseEnrollment, Message

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        try:
            user = User.objects.get(username=username)
            if check_password(password, user.password_hash):
                request.session['user_id'] = user.id
                request.session['username'] = user.username
                request.session['role'] = user.role
                return redirect('courses')
            else:
                messages.error(request, "Invalid credentials.")
        except User.DoesNotExist:
            messages.error(request, "User does not exist.")
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
        
        if password != password_confirm:
            messages.error(request, "Passwords do not match.")
            return render(request, 'register.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return render(request, 'register.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email is already registered.")
            return render(request, 'register.html')
        
        hashed_password = make_password(password)
        user = User.objects.create(
            username=username,
            email=email,
            password_hash=hashed_password,
            role=role  
        )
        messages.success(request, "Registration successful!")
        
        request.session['user_id'] = user.id
        request.session['username'] = user.username
        request.session['role'] = user.role
        
        return redirect('courses')
        
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
    user = User.objects.get(id=user_id)
    
    if user.role != 'teacher':
        messages.error(request, "Only teachers can create courses.")
        return redirect('courses')
    
    # Get enrolled courses for sidebar
    enrolled_courses = Course.objects.filter(owner=user).order_by('-created_at')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        
        if not title:
            messages.error(request, "Title is required.")
            return render(request, 'create_course.html', {'enrolled_courses': enrolled_courses})
            
        course = Course(title=title, description=description, owner=user)
        course.save()
        
        messages.success(request, f"Course created successfully! Enrollment code: {course.enrollment_code}")
        
        return redirect('courses')
        
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
    
    # Get all enrolled courses for the sidebar
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
        'active_course': course  # Mark the current course as active
    })

def create_activity_view(request, course_id):
    if not request.session.get('user_id'):
        return redirect('login')
    try:
        course = Course.objects.get(id=course_id)
        user_id = request.session.get('user_id')
        user = User.objects.get(id=user_id)
        can_create_activity = course.owner_id == user_id and user.role == 'teacher'
        if not can_create_activity:
            messages.error(request, "Only teachers can create activities in this course.")
            return redirect('activities')
        if request.method == 'POST':
            activity_title = request.POST.get('activity_title', '')
            description = request.POST.get('activity_description', '')
            expert_mode = request.POST.get('expert_mode') == 'on'
            custom_prompt = request.POST.get('custom_prompt', '') if expert_mode else ''
            questions = request.POST.getlist('questions[]') or []
            agent_attitude = request.POST.get('agent_attitude', 'friendly')
            subjects = request.POST.get('subjects', '')
            restrict_to_subject = request.POST.get('restrict_to_subject') == 'on'
            allow_questions = request.POST.get('allow_questions') == 'on'
            allow_emojis = request.POST.get('allow_emojis') == 'on'
            trust_document = request.POST.get('trust_document') == 'on'
            activity = Activity.objects.create(
                course=course,
                user=user,
                title=activity_title if activity_title else f"Activity for {course.title}",
                description=description,
                expert_mode=expert_mode,
                custom_prompt=custom_prompt,
                questions=questions,
                agent_attitude=agent_attitude,
                subjects=subjects,
                restrict_to_subject=restrict_to_subject,
                allow_questions=allow_questions,
                allow_emojis=allow_emojis,
                trust_document=trust_document
            )
            messages.success(request, "Activity created successfully!")
            return redirect('activities')
        else:
            return redirect('activities')
    except Course.DoesNotExist:
        messages.error(request, "Course not found.")
        return redirect('courses')


def join_course_view(request):
    """View for students to join courses using enrollment codes"""
    if not request.session.get('user_id'):
        return redirect('login')
        
    user_id = request.session.get('user_id')
    user = User.objects.get(id=user_id)
    
    # Get enrolled courses for sidebar
    enrolled_courses = Course.objects.filter(enrollments__user=user).order_by('-created_at')
    
    if request.method == 'POST':
        enrollment_code = request.POST.get('enrollment_code')
        
        if not enrollment_code:
            messages.error(request, "Enrollment code is required.")
            return render(request, 'join_course.html', {'enrolled_courses': enrolled_courses}) 
            
        try:
            course = Course.objects.get(enrollment_code=enrollment_code)
            
            # Check if already enrolled
            if CourseEnrollment.objects.filter(user=user, course=course).exists():
                messages.warning(request, f"You are already enrolled in the course '{course.title}'.")
            else:
                # Create enrollment
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
    # Ensure user is logged in and is a teacher
    if not request.session.get('user_id'):
        return redirect('login')
    user_id = request.session.get('user_id')
    user = User.objects.get(id=user_id)
    if user.role != 'teacher':
        messages.error(request, "Only teachers can access the dashboard.")
        return redirect('courses')

    # Get teacher's courses and selected course
    courses = Course.objects.filter(owner=user).order_by('-created_at')
    selected_course_id = request.GET.get('course_id')
    if selected_course_id:
        selected_course = courses.filter(id=selected_course_id).first()
    else:
        selected_course = courses.first()
    if not selected_course:
        messages.info(request, "No courses found. Create one first.")
        return redirect('create_course')

    # Compute stats for the selected course
    students = CourseEnrollment.objects.filter(course=selected_course).select_related('user')
    activities_count = Activity.objects.filter(course=selected_course).count()
    student_messages_qs = Message.objects.filter(
        thread__activity__course=selected_course,
        role='student'
    ).select_related('thread__user')
    total_messages = student_messages_qs.count()

    # Aggregate per-student message counts and average lengths
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

    # Recent messages preview
    last_messages = student_messages_qs.order_by('-timestamp')[:10]

    # Prepare context and render template
    context = {
        'courses': courses,
        'selected_course': selected_course,
        'students_count': students.count(),
        'activities_count': activities_count,
        'total_messages': total_messages,
        'stats_per_student': stats_per_student,
        'last_messages': last_messages,
        'enrolled_courses': courses  # Add enrolled_courses to context
    }
    return render(request, 'dashboard.html', context)
    
def edit_course_view(request, course_id):
    """View for teachers to edit their courses"""
    if not request.session.get('user_id'):
        return redirect('login')
        
    user_id = request.session.get('user_id')
    user = User.objects.get(id=user_id)
    
    # Only teachers can edit courses
    if user.role != 'teacher':
        messages.error(request, "Only teachers can edit courses.")
        return redirect('courses')
    
    # Get enrolled courses for sidebar
    enrolled_courses = Course.objects.filter(owner=user).order_by('-created_at')
    
    try:
        course = Course.objects.get(id=course_id)
        
        # Only the owner of the course can edit it
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
        # For teachers, show activities they created
        teacher_courses = Course.objects.filter(owner_id=user_id)
        activities = Activity.objects.filter(course__in=teacher_courses).order_by('-created_at')
        context = {
            'activities': activities,
            'is_teacher': True,
            'courses': teacher_courses,
            'enrolled_courses': teacher_courses
        }
    else:
        # For students, show activities from enrolled courses
        enrolled_courses = Course.objects.filter(enrollments__user=user)
        activities = Activity.objects.filter(course__in=enrolled_courses).order_by('-created_at')
        context = {
            'activities': activities,
            'is_teacher': False,
            'courses': enrolled_courses,
            'enrolled_courses': enrolled_courses
        }
    
    return render(request, 'activities.html', context)
