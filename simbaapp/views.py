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
                lang = request.session.get('lang', 'fr')
                error_messages = {
                    'en': "Invalid credentials.",
                    'es': "Credenciales inválidas.",
                    'fr': "Identifiants invalides."
                }
                messages.error(request, error_messages.get(lang, error_messages['fr']))
        except User.DoesNotExist:
            lang = request.session.get('lang', 'fr')
            error_messages = {
                'en': "User does not exist.",
                'es': "El usuario no existe.",
                'fr': "L'utilisateur n'existe pas."
            }
            messages.error(request, error_messages.get(lang, error_messages['fr']))
    return render(request, 'login.html')

def logout_view(request):
    request.session.flush()
    lang = request.session.get('lang', 'fr')
    success_messages = {
        'en': "Successfully logged out!",
        'es': "¡Sesión cerrada con éxito!",
        'fr': "Déconnexion réussie !"
    }
    messages.success(request, success_messages.get(lang, success_messages['fr']))
    return redirect('login')

def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        role = request.POST.get('role', 'student')  # Captura o papel selecionado pelo usuário
        
        lang = request.session.get('lang', 'fr')
        
        if password != password_confirm:
            error_messages = {
                'en': "Passwords do not match.",
                'es': "Las contraseñas no coinciden.",
                'fr': "Les mots de passe ne correspondent pas."
            }
            messages.error(request, error_messages.get(lang, error_messages['fr']))
            return render(request, 'register.html')
        
        if User.objects.filter(username=username).exists():
            error_messages = {
                'en': "Username already exists.",
                'es': "El nombre de usuario ya existe.",
                'fr': "Le nom d'utilisateur existe déjà."
            }
            messages.error(request, error_messages.get(lang, error_messages['fr']))
            return render(request, 'register.html')
        
        if User.objects.filter(email=email).exists():
            error_messages = {
                'en': "Email is already registered.",
                'es': "El correo electrónico ya está registrado.",
                'fr': "L'email est déjà enregistré."
            }
            messages.error(request, error_messages.get(lang, error_messages['fr']))
            return render(request, 'register.html')
        
        hashed_password = make_password(password)
        user = User.objects.create(
            username=username,
            email=email,
            password_hash=hashed_password,
            role=role  
        )
        success_messages = {
            'en': "Registration successful!",
            'es': "¡Registro exitoso!",
            'fr': "Inscription réussie !"
        }
        messages.success(request, success_messages.get(lang, success_messages['fr']))
        
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
            'chainlit_url': f"http://localhost:8500/?activity_id={activity_id}&user_id={user_id}&username={urllib.parse.quote(request.session.get('username', 'User'))}&lang={request.session.get('lang', 'fr')}"
        }
        return render(request, 'chainlit.html', context)
    except Activity.DoesNotExist:
        lang = request.session.get('lang', 'fr')
        error_messages = {
            'en': "Activity not found.",
            'es': "Actividad no encontrada.",
            'fr': "Activité non trouvée."
        }
        messages.error(request, error_messages.get(lang, error_messages['fr']))
        return redirect('courses')

def courses_view(request):
    if not request.session.get('user_id'):
        return redirect('login')
    
    user_id = request.session.get('user_id')
    role = request.session.get('role')
    
    if role == 'teacher':
        user = User.objects.get(id=user_id)
        courses = Course.objects.filter(owner_id=user_id).order_by('-created_at')
        
        lang = request.session.get('lang', 'fr')
        debug_messages = {
            'en': f"Logged in as teacher: {user.username}",
            'es': f"Conectado como profesor: {user.username}",
            'fr': f"Connecté en tant que professeur: {user.username}"
        }
        messages.info(request, debug_messages.get(lang, debug_messages['fr']))
        
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
        lang = request.session.get('lang', 'fr')
        error_messages = {
            'en': "Only teachers can create courses.",
            'es': "Solo los profesores pueden crear cursos.",
            'fr': "Seuls les enseignants peuvent créer des cours."
        }
        messages.error(request, error_messages.get(lang, error_messages['fr']))
        return redirect('courses')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        
        if not title:
            lang = request.session.get('lang', 'fr')
            error_messages = {
                'en': "Title is required.",
                'es': "El título es obligatorio.",
                'fr': "Le titre est obligatoire."
            }
            messages.error(request, error_messages.get(lang, error_messages['fr']))
            return render(request, 'create_course.html')
            
        course = Course(title=title, description=description, owner=user)
        course.save()
        
        lang = request.session.get('lang', 'fr')
        success_messages = {
            'en': f"Course created successfully! Enrollment code: {course.enrollment_code}",
            'es': f"¡Curso creado con éxito! Código de inscripción: {course.enrollment_code}",
            'fr': f"Cours créé avec succès ! Code d'inscription : {course.enrollment_code}"
        }
        messages.success(request, success_messages.get(lang, success_messages['fr']))
        
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
        lang = request.session.get('lang', 'fr')
        error_messages = {
            'en': "Course not found.",
            'es': "Curso no encontrado.",
            'fr': "Cours non trouvé."
        }
        messages.error(request, error_messages.get(lang, error_messages['fr']))
        return redirect('courses')
        
    has_access = False
    is_teacher_of_course = False

    if course.owner_id == user_id and user.role == 'teacher':
        has_access = True
        is_teacher_of_course = True
    elif CourseEnrollment.objects.filter(user=user, course=course).exists():
        has_access = True

    if not has_access:
        lang = request.session.get('lang', 'fr')
        error_messages = {
            'en': "You do not have permission to access this course.",
            'es': "No tienes permiso para acceder a este curso.",
            'fr': "Vous n'avez pas la permission d'accéder à ce cours."
        }
        messages.error(request, error_messages.get(lang, error_messages['fr']))
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
            lang = request.session.get('lang', 'fr')
            error_messages = {
                'en': "Only teachers can create activities in this course.",
                'es': "Solo los profesores pueden crear actividades en este curso.",
                'fr': "Seuls les enseignants peuvent créer des activités dans ce cours."
            }
            messages.error(request, error_messages.get(lang, error_messages['fr']))
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
            lang = request.session.get('lang', 'fr')
            success_messages = {
                'en': "Activity created successfully!",
                'es': "¡Actividad creada con éxito!",
                'fr': "Activité créée avec succès !"
            }
            messages.success(request, success_messages.get(lang, success_messages['fr']))
            return redirect('course_detail', course_id=course.id)
        else:
            return redirect('course_detail', course_id=course.id)
    except Course.DoesNotExist:
        lang = request.session.get('lang', 'fr')
        error_messages = {
            'en': "Course not found.",
            'es': "Curso no encontrado.",
            'fr': "Cours non trouvé."
        }
        messages.error(request, error_messages.get(lang, error_messages['fr']))
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
            lang = request.session.get('lang', 'fr')
            error_messages = {
                'en': "Enrollment code is required.",
                'es': "Se requiere el código de inscripción.",
                'fr': "Le code d'inscription est requis."
            }
            messages.error(request, error_messages.get(lang, error_messages['fr']))
            return render(request, 'join_course.html') 
            
        try:
            course = Course.objects.get(enrollment_code=enrollment_code)
            
            # Check if already enrolled
            if CourseEnrollment.objects.filter(user=user, course=course).exists():
                lang = request.session.get('lang', 'fr')
                warning_messages = {
                    'en': f"You are already enrolled in the course '{course.title}'.",
                    'es': f"Ya estás inscrito en el curso '{course.title}'.",
                    'fr': f"Vous êtes déjà inscrit au cours '{course.title}'."
                }
                messages.warning(request, warning_messages.get(lang, warning_messages['fr']))
            else:
                # Create enrollment
                CourseEnrollment.objects.create(
                    user=user,
                    course=course
                )
                
                lang = request.session.get('lang', 'fr')
                success_messages = {
                    'en': f"Successfully enrolled in course '{course.title}'!",
                    'es': f"¡Inscrito con éxito en el curso '{course.title}'!",
                    'fr': f"Inscrit avec succès au cours '{course.title}' !"
                }
                messages.success(request, success_messages.get(lang, success_messages['fr']))
            
            return redirect('course_detail', course_id=course.id)
            
        except Course.DoesNotExist:
            lang = request.session.get('lang', 'fr')
            error_messages = {
                'en': "Invalid enrollment code.",
                'es': "Código de inscripción inválido.",
                'fr': "Code d'inscription invalide."
            }
            messages.error(request, error_messages.get(lang, error_messages['fr']))
            return render(request, 'join_course.html') 
            
    return render(request, 'join_course.html')
