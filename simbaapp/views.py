# filepath: /Users/lenonanthony/Documents/simba-2025/simbaapp/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
import urllib
from .models import User, Course, Activity, CourseEnrollment

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
            'is_teacher': True
        }
    else:
        user = User.objects.get(id=user_id)
        courses = Course.objects.filter(enrollments__user=user).order_by('-created_at')
        context = {
            'courses': courses,
            'is_teacher': False
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
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        
        if not title:
            messages.error(request, "Title is required.")
            return render(request, 'create_course.html')
            
        course = Course(title=title, description=description, owner=user)
        course.save()
        
        messages.success(request, f"Course created successfully! Enrollment code: {course.enrollment_code}")
        
        return redirect('course_detail', course_id=course.id)
        
    return render(request, 'create_course.html')

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
    
    return render(request, 'course_detail.html', { 
        'course': course, 
        'activities': activities,
        'is_teacher': is_teacher_of_course,
        'participants': participants
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
            return redirect('course_detail', course_id=course.id)
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
            return redirect('course_detail', course_id=course.id)
        else:
            return redirect('course_detail', course_id=course.id)
    except Course.DoesNotExist:
        messages.error(request, "Course not found.")
        return redirect('courses')


def join_course_view(request):
    """View for students to join courses using enrollment codes"""
    if not request.session.get('user_id'):
        return redirect('login')
        
    user_id = request.session.get('user_id')
    user = User.objects.get(id=user_id)
    
    if request.method == 'POST':
        enrollment_code = request.POST.get('enrollment_code')
        
        if not enrollment_code:
            messages.error(request, "Enrollment code is required.")
            return render(request, 'join_course.html') 
            
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
            
            return redirect('course_detail', course_id=course.id)
            
        except Course.DoesNotExist:
            messages.error(request, "Invalid enrollment code.")
            return render(request, 'join_course.html') 
            
    return render(request, 'join_course.html')
