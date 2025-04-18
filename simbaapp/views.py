from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
import urllib
from .models import User, Course, Activity, Classroom, ClassEnrollment, Topic, CourseEnrollment

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
        classrooms = Classroom.objects.filter(teacher_id=user_id)
        
        lang = request.session.get('lang', 'fr')
        debug_messages = {
            'en': f"Logged in as teacher: {user.username}",
            'es': f"Conectado como profesor: {user.username}",
            'fr': f"Connecté en tant que professeur: {user.username}"
        }
        messages.info(request, debug_messages.get(lang, debug_messages['fr']))
        
        context = {
            'courses': courses,
            'classrooms': classrooms,
            'is_teacher': True
        }
    else:
        user = User.objects.get(id=user_id)
        enrollments = ClassEnrollment.objects.filter(user=user)
        classroom_ids = [enrollment.classroom.id for enrollment in enrollments]
        classroom_topics = Topic.objects.filter(classroom_id__in=classroom_ids)
        classroom_courses = Course.objects.filter(topic__in=classroom_topics)
        
        direct_enrollments = CourseEnrollment.objects.filter(user=user)
        directly_enrolled_course_ids = [enrollment.course.id for enrollment in direct_enrollments]
        directly_enrolled_courses = Course.objects.filter(id__in=directly_enrolled_course_ids)

        all_courses = set(classroom_courses) | set(directly_enrolled_courses)
        sorted_courses = sorted(list(all_courses), key=lambda course: course.created_at, reverse=True)

        context = {
            'courses': sorted_courses,
            'is_teacher': False,
            'enrolled_classrooms': enrollments
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
    
    classrooms = Classroom.objects.filter(teacher=user)
    topics = Topic.objects.filter(classroom__in=classrooms)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        topic_id = request.POST.get('topic')
        
        if not title:
            lang = request.session.get('lang', 'fr')
            error_messages = {
                'en': "Title is required.",
                'es': "El título es obligatorio.",
                'fr': "Le titre est obligatoire."
            }
            messages.error(request, error_messages.get(lang, error_messages['fr']))
            return render(request, 'create_course.html', {'topics': topics})
            
        course = Course(
            title=title,
            description=description,
            owner=user
        )
        
        if topic_id:
            try:
                topic = Topic.objects.get(id=topic_id)
                course.topic = topic
            except Topic.DoesNotExist:
                pass
                
        course.save()
        
        lang = request.session.get('lang', 'fr')
        success_messages = {
            'en': f"Course created successfully! Enrollment code: {course.enrollment_code}",
            'es': f"¡Curso creado con éxito! Código de inscripción: {course.enrollment_code}",
            'fr': f"Cours créé avec succès ! Code d'inscription : {course.enrollment_code}"
        }
        messages.success(request, success_messages.get(lang, success_messages['fr']))
        
        return redirect('course_detail', course_id=course.id)
        
    return render(request, 'create_course.html', {'topics': topics})

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

    if course.owner_id == user_id:
        has_access = True
        if user.role == 'teacher':
             is_teacher_of_course = True
    
    elif hasattr(course, 'topic') and course.topic:
        if user.role == 'teacher' and course.topic.classroom.teacher_id == user_id:
            has_access = True
            is_teacher_of_course = True
        elif ClassEnrollment.objects.filter(
            user=user, 
            classroom=course.topic.classroom
        ).exists():
             has_access = True
             
    if not has_access:
        if CourseEnrollment.objects.filter(user=user, course=course).exists():
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
        
        can_create_activity = False
        if course.owner_id == user_id and user.role == 'teacher':
             can_create_activity = True
        elif hasattr(course, 'topic') and course.topic and user.role == 'teacher' and course.topic.classroom.teacher_id == user_id:
             can_create_activity = True

        if not can_create_activity:
            lang = request.session.get('lang', 'fr')
            error_messages = {
                'en': "Only teachers can create activities in this course.",
                'es': "Solo los profesores pueden crear actividades en este curso.",
                'fr': "Seuls les enseignants peuvent créer des activités dans ce cours."
            }
            messages.error(request, error_messages.get(lang, error_messages['fr']))
            return redirect('course_detail', course_id=course.id) 
            
        activity_title = None
        if request.method == 'POST':
            activity_title = request.POST.get('activity_title', '')  
            
            activity = Activity.objects.create(
                course=course, 
                user=user,
                title=activity_title if activity_title else f"Activity for {course.title}"
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

def classrooms_view(request):
    if not request.session.get('user_id'):
        return redirect('login')
        
    user_id = request.session.get('user_id')
    role = request.session.get('role')
    
    if role == 'teacher':
        classrooms = Classroom.objects.filter(teacher_id=user_id).order_by('-created_at')
        context = {
            'classrooms': classrooms,
            'is_teacher': True
        }
    else:
        enrollments = ClassEnrollment.objects.filter(user_id=user_id)
        classrooms = [enrollment.classroom for enrollment in enrollments]
        context = {
            'classrooms': classrooms,
            'is_teacher': False
        }
    
    return render(request, 'classrooms.html', context)

def create_classroom_view(request):
    if not request.session.get('user_id'):
        return redirect('login')
        
    if request.session.get('role') != 'teacher':
        lang = request.session.get('lang', 'fr')
        error_messages = {
            'en': "Only teachers can create courses.",
            'es': "Solo los profesores pueden crear cursos.",
            'fr': "Seuls les enseignants peuvent créer des cours."
        }
        messages.error(request, error_messages.get(lang, error_messages['fr']))
        return redirect('courses')
    # Resto da função permanece igual...

def classroom_detail_view(request, classroom_id):
    if not request.session.get('user_id'):
        return redirect('login')
        
    try:
        classroom = Classroom.objects.get(id=classroom_id)
        user_id = request.session.get('user_id')
        user = User.objects.get(id=user_id)
        
        has_access = False
        is_teacher = False
        
        if classroom.teacher_id == user_id:
            has_access = True
            is_teacher = True
        elif ClassEnrollment.objects.filter(user=user, classroom=classroom).exists():
            has_access = True
            
        if not has_access:
            lang = request.session.get('lang', 'fr')
            error_messages = {
                'en': "You do not have permission to access this classroom.",
                'es': "No tienes permiso para acceder a esta aula.",
                'fr': "Vous n'avez pas la permission d'accéder à cette salle de classe."
            }
            messages.error(request, error_messages.get(lang, error_messages['fr']))
            return redirect('classrooms')
            
        # Obter tópicos da sala de aula
        topics = Topic.objects.filter(classroom=classroom).order_by('-created_at')
        
        # Obter alunos matriculados na sala de aula
        enrollments = ClassEnrollment.objects.filter(classroom=classroom).select_related('user')
        
        context = {
            'classroom': classroom,
            'topics': topics,
            'is_teacher': is_teacher,
            'enrollments': enrollments
        }
        
        return render(request, 'classroom_detail.html', context)
        
    except Classroom.DoesNotExist:
        lang = request.session.get('lang', 'fr')
        error_messages = {
            'en': "Classroom not found.",
            'es': "Aula no encontrada.",
            'fr': "Salle de classe non trouvée."
        }
        messages.error(request, error_messages.get(lang, error_messages['fr']))
        return redirect('classrooms')

def create_topic_view(request, classroom_id):
    if not request.session.get('user_id'):
        return redirect('login')
    
    try:
        classroom = Classroom.objects.get(id=classroom_id)
        user_id = request.session.get('user_id')
        user = User.objects.get(id=user_id)
        
        # Verificar se o usuário é professor da sala de aula
        if classroom.teacher_id != user_id or user.role != 'teacher':
            lang = request.session.get('lang', 'fr')
            error_messages = {
                'en': "Only teachers can create topics in this classroom.",
                'es': "Solo los profesores pueden crear temas en esta aula.",
                'fr': "Seuls les enseignants peuvent créer des sujets dans cette salle de classe."
            }
            messages.error(request, error_messages.get(lang, error_messages['fr']))
            return redirect('classroom_detail', classroom_id=classroom.id)
        
        if request.method == 'POST':
            title = request.POST.get('title')
            description = request.POST.get('description')
            prompt = request.POST.get('prompt')
            
            if not title:
                lang = request.session.get('lang', 'fr')
                error_messages = {
                    'en': "Title is required.",
                    'es': "El título es obligatorio.",
                    'fr': "Le titre est obligatoire."
                }
                messages.error(request, error_messages.get(lang, error_messages['fr']))
                return render(request, 'create_topic.html', {'classroom': classroom})
            
            topic = Topic.objects.create(
                title=title,
                description=description,
                prompt=prompt,
                classroom=classroom
            )
            
            lang = request.session.get('lang', 'fr')
            success_messages = {
                'en': "Topic created successfully!",
                'es': "¡Tema creado con éxito!",
                'fr': "Sujet créé avec succès!"
            }
            messages.success(request, success_messages.get(lang, success_messages['fr']))
            return redirect('classroom_detail', classroom_id=classroom.id)
            
        return render(request, 'create_topic.html', {'classroom': classroom})
        
    except Classroom.DoesNotExist:
        lang = request.session.get('lang', 'fr')
        error_messages = {
            'en': "Classroom not found.",
            'es': "Aula no encontrada.",
            'fr': "Salle de classe non trouvée."
        }
        messages.error(request, error_messages.get(lang, error_messages['fr']))
        return redirect('classrooms')

def enroll_classroom_view(request):
    """View for students to join classrooms using enrollment codes"""
    if not request.session.get('user_id'):
        return redirect('login')
        
    user_id = request.session.get('user_id')
    user = User.objects.get(id=user_id)
    
    if request.method == 'POST':
        classroom_code = request.POST.get('classroom_code')
        
        if not classroom_code:
            lang = request.session.get('lang', 'fr')
            error_messages = {
                'en': "Enrollment code is required.",
                'es': "Se requiere el código de inscripción.",
                'fr': "Le code d'inscription est requis."
            }
            messages.error(request, error_messages.get(lang, error_messages['fr']))
            return render(request, 'enroll_classroom.html')
            
        try:
            classroom = Classroom.objects.get(id=classroom_code)
            
            # Check if already enrolled
            if ClassEnrollment.objects.filter(user=user, classroom=classroom).exists():
                lang = request.session.get('lang', 'fr')
                warning_messages = {
                    'en': f"You are already enrolled in the classroom '{classroom.name}'.",
                    'es': f"Ya estás inscrito en el aula '{classroom.name}'.",
                    'fr': f"Vous êtes déjà inscrit à la salle de classe '{classroom.name}'."
                }
                messages.warning(request, warning_messages.get(lang, warning_messages['fr']))
            else:
                # Create enrollment
                ClassEnrollment.objects.create(
                    user=user,
                    classroom=classroom,
                    role='student'
                )
                
                lang = request.session.get('lang', 'fr')
                success_messages = {
                    'en': f"Successfully enrolled in classroom '{classroom.name}'!",
                    'es': f"¡Inscrito con éxito en el aula '{classroom.name}'!",
                    'fr': f"Inscrit avec succès à la salle de classe '{classroom.name}' !"
                }
                messages.success(request, success_messages.get(lang, success_messages['fr']))
            
            return redirect('classroom_detail', classroom_id=classroom.id)
            
        except Classroom.DoesNotExist:
            lang = request.session.get('lang', 'fr')
            error_messages = {
                'en': "Invalid enrollment code.",
                'es': "Código de inscripción inválido.",
                'fr': "Code d'inscription invalide."
            }
            messages.error(request, error_messages.get(lang, error_messages['fr']))
            return render(request, 'enroll_classroom.html')
            
    return render(request, 'enroll_classroom.html')

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
