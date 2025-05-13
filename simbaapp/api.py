import os
import django
import django.apps
from django.contrib.auth.hashers import make_password, check_password
from .models import User, Course, Activity, Thread, Message, CourseEnrollment
from ninja import Swagger, Router
from ninja_extra import NinjaExtraAPI
from ninja_jwt.controller import NinjaJWTDefaultController
from typing import List
from django.db.models import Max
from .schemas import (
    SignInSchema,
    MessageSchema,
    UserRegisterSchema, 
    UserOutSchema,      
    UserUpdateSchema,
    ErrorSchema,       
    CourseCreateSchema,
    CourseUpdateSchema,
    CourseOutSchema,
    ActivityCreateSchema,
    ActivityUpdateSchema,
    ActivityOutSchema,
    ThreadGetOrCreateSchema,
    MessageCreateSchema,
    ThreadSchema,
    ActivityDetailSchema
)

from django.shortcuts import get_object_or_404
from http import HTTPStatus

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'simba.settings')
if not django.apps.apps.ready:
    django.setup()

api = NinjaExtraAPI(csrf=False, docs=Swagger(settings={"persistAuthorization": True}))
api.register_controllers(NinjaJWTDefaultController)


@api.post("/auth/register", response={201: UserOutSchema, 400: ErrorSchema, 409: ErrorSchema})
def register_user(request, payload: UserRegisterSchema):
    """
    Register a new user.
    """
    if payload.password != payload.password_confirm:
        return HTTPStatus.BAD_REQUEST, {"message": "Passwords do not match."}
        
    if User.objects.filter(username=payload.username).exists():
        return HTTPStatus.CONFLICT, {"message": "Username already exists."}
        
    if User.objects.filter(email=payload.email).exists():
        return HTTPStatus.CONFLICT, {"message": "Email is already registered."}
        
    try:
        hashed_password = make_password(payload.password)
        user = User.objects.create(
            username=payload.username,
            email=payload.email,
            password_hash=hashed_password,
            role=payload.role
        )
        return HTTPStatus.CREATED, user
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Registration failed: {str(e)}"}

@api.post("/auth/login", response={200: UserOutSchema, 401: ErrorSchema, 404: ErrorSchema})
def login_user(request, payload: SignInSchema):
    """
    Authenticate a user and return user details.
    """
    try:
        user = User.objects.get(username=payload.username)
        if check_password(payload.password, user.password_hash):
            return HTTPStatus.OK, user
        else:
            return HTTPStatus.UNAUTHORIZED, {"message": "Invalid credentials."}
    except User.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "User does not exist."}
    except Exception as e:
         return HTTPStatus.INTERNAL_SERVER_ERROR, {"message": f"Login failed: {str(e)}"}

@api.put("/users/{user_id}", response={200: UserOutSchema, 400: ErrorSchema, 401: ErrorSchema, 404: ErrorSchema, 409: ErrorSchema})
def update_user_profile(request, user_id: int, payload: UserUpdateSchema):
    """
    Update a user's profile information.
    The current password is required to make any changes.
    """
    try:
        user = User.objects.get(id=user_id)
        
        if not check_password(payload.current_password, user.password_hash):
            return HTTPStatus.UNAUTHORIZED, {"message": "Current password is incorrect."}
            
        if payload.username != user.username and User.objects.filter(username=payload.username).exists():
            return HTTPStatus.CONFLICT, {"message": "Username already exists."}
            
        if payload.email != user.email and User.objects.filter(email=payload.email).exists():
            return HTTPStatus.CONFLICT, {"message": "Email is already registered."}
        
        if payload.new_password:
            if not payload.new_password_confirm:
                return HTTPStatus.BAD_REQUEST, {"message": "Password confirmation is required."}
                
            if payload.new_password != payload.new_password_confirm:
                return HTTPStatus.BAD_REQUEST, {"message": "New passwords do not match."}
                
            user.password_hash = make_password(payload.new_password)
        
        user.username = payload.username
        user.email = payload.email
        user.save()
        
        return HTTPStatus.OK, user
    except User.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "User not found."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Profile update failed: {str(e)}"}

# --- Course CRUD ---
@api.post("/courses", response={201: CourseOutSchema, 400: ErrorSchema, 403: ErrorSchema})
def create_course_api(request, payload: CourseCreateSchema, user_id: int):
    """
    Create a new course. user_id is passed for now.
    Ideally, this would come from an authenticated token.
    """
    try:
        user = User.objects.get(id=user_id)
        if user.role != 'teacher':
            return HTTPStatus.FORBIDDEN, {"message": "Only teachers can create courses."}
        
        course = Course.objects.create(
            title=payload.title,
            description=payload.description,
            owner=user
        )
        return HTTPStatus.CREATED, course
    except User.DoesNotExist:
        return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Course creation failed: {str(e)}"}

@api.put("/courses/{course_id}", response={200: CourseOutSchema, 400: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema})
def update_course_api(request, course_id: int, payload: CourseUpdateSchema, user_id: int):
    """
    Update an existing course. Only the owner/teacher can update it.
    """
    try:
        user = User.objects.get(id=user_id)
        course = Course.objects.get(id=course_id)
        
        if course.owner_id != user.id or user.role != 'teacher':
            return HTTPStatus.FORBIDDEN, {"message": "Only the course owner can update this course."}
        
        course.title = payload.title
        course.description = payload.description if payload.description else course.description
        course.save()
        
        return HTTPStatus.OK, course
    except User.DoesNotExist:
        return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except Course.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Course not found."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Course update failed: {str(e)}"}

@api.delete("/courses/{course_id}", response={204: None, 403: ErrorSchema, 404: ErrorSchema})
def delete_course_api(request, course_id: int, user_id: int):
    """
    Delete a course. Only the owner/teacher can delete it.
    """
    try:
        user = User.objects.get(id=user_id)
        course = Course.objects.get(id=course_id)
        
        if course.owner_id != user.id or user.role != 'teacher':
            return HTTPStatus.FORBIDDEN, {"message": "Only the course owner can delete this course."}
        
        course.delete()
        
        return HTTPStatus.NO_CONTENT, None
    except User.DoesNotExist:
        return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except Course.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Course not found."}
    except Exception as e:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"message": f"Course deletion failed: {str(e)}"}

# --- Activity CRUD ---
@api.post("/activities", response={201: ActivityOutSchema, 400: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema})
def create_activity_api(request, payload: ActivityCreateSchema, user_id: int):
    """
    Create a new activity. user_id is passed for now.
    """
    try:
        user = User.objects.get(id=user_id)
        course = Course.objects.get(id=payload.course_id)

        if course.owner_id != user.id or user.role != 'teacher':
            return HTTPStatus.FORBIDDEN, {"message": "Only the course teacher can create activities."}

        activity = Activity.objects.create(
            course=course,
            user=user,
            title=payload.title if payload.title else f"Activity for {course.title}",
            description=payload.description,
            expert_mode=payload.expert_mode,
            custom_prompt=payload.custom_prompt,
            questions=payload.questions,
            agent_attitude=payload.agent_attitude,
            subjects=payload.subjects,
            restrict_to_subject=payload.restrict_to_subject,
            allow_questions=payload.allow_questions,
            allow_emojis=payload.allow_emojis,
            trust_document=payload.trust_document,
            word_limit=payload.word_limit
        )
        return HTTPStatus.CREATED, activity
    except User.DoesNotExist:
        return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except Course.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Course not found."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Activity creation failed: {str(e)}"}

@api.put("/activities/{activity_id}", response={200: ActivityOutSchema, 400: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema})
def update_activity_api(request, activity_id: int, payload: ActivityUpdateSchema, user_id: int):
    """
    Update an existing activity. Only the course owner/teacher can update it.
    """
    try:
        user = User.objects.get(id=user_id)
        activity = Activity.objects.select_related('course').get(id=activity_id)
        
        # Check if user is the owner of the course
        if activity.course.owner_id != user.id or user.role != 'teacher':
            return HTTPStatus.FORBIDDEN, {"message": "Only the course owner can update this activity."}
        
        # Update activity fields
        activity.title = payload.title if payload.title is not None else activity.title
        activity.description = payload.description if payload.description is not None else activity.description
        activity.expert_mode = payload.expert_mode
        activity.custom_prompt = payload.custom_prompt
        activity.questions = payload.questions
        activity.agent_attitude = payload.agent_attitude
        activity.subjects = payload.subjects
        activity.restrict_to_subject = payload.restrict_to_subject
        activity.allow_questions = payload.allow_questions
        activity.allow_emojis = payload.allow_emojis
        activity.trust_document = payload.trust_document
        activity.word_limit = payload.word_limit
        
        activity.save()
        
        return HTTPStatus.OK, activity
    except User.DoesNotExist:
        return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except Activity.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Activity not found."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Activity update failed: {str(e)}"}

@api.delete("/activities/{activity_id}", response={204: None, 403: ErrorSchema, 404: ErrorSchema})
def delete_activity_api(request, activity_id: int, user_id: int):
    """
    Delete an activity. Only the course owner/teacher can delete it.
    """
    try:
        user = User.objects.get(id=user_id)
        activity = Activity.objects.select_related('course').get(id=activity_id)
        
        # Check if user is the owner of the course
        if activity.course.owner_id != user.id or user.role != 'teacher':
            return HTTPStatus.FORBIDDEN, {"message": "Only the course owner can delete this activity."}
        
        # Delete the activity
        activity.delete()
        
        return HTTPStatus.NO_CONTENT, None
    except User.DoesNotExist:
        return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except Activity.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Activity not found."}
    except Exception as e:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"message": f"Activity deletion failed: {str(e)}"}

@api.get("/activities/{activity_id}", response={200: ActivityDetailSchema, 404: ErrorSchema})
def get_activity_api(request, activity_id: int):
    """Fetch details for a specific activity."""
    try:
        activity = Activity.objects.get(id=activity_id)
        return HTTPStatus.OK, activity
    except Activity.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Activity not found."}
    except Exception as e:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"message": f"Failed to get activity: {str(e)}"}

# --- Thread and Message Endpoints for Chainlit --- 

thread_router = Router() 

@thread_router.post("/get-or-create", response={200: ThreadSchema, 201: ThreadSchema, 400: ErrorSchema, 404: ErrorSchema})
def get_or_create_thread_api(request, payload: ThreadGetOrCreateSchema):
    """Get an existing thread or create a new one."""
    try:
        activity = Activity.objects.get(id=payload.activity_id)
        
        thread, created = Thread.objects.get_or_create(
            activity=activity,
            user_id=payload.user_id, 
        )
        
        status_code = HTTPStatus.CREATED if created else HTTPStatus.OK
        if not created:
             thread.save(update_fields=['updated_at'])
             
        return status_code, thread
        
    except Activity.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Activity not found."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Thread operation failed: {str(e)}"}

@thread_router.get("/{thread_id}/messages", response={200: List[MessageSchema], 404: ErrorSchema})
def get_messages_api(request, thread_id: int):
    """Get all messages for a specific thread."""
    try:
        thread = Thread.objects.get(id=thread_id)
        messages = Message.objects.filter(thread=thread).order_by('message_number')
        return HTTPStatus.OK, list(messages)
    except Thread.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Thread not found."}
    except Exception as e:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"message": f"Failed to get messages: {str(e)}"}

@thread_router.post("/{thread_id}/messages", response={201: MessageSchema, 400: ErrorSchema, 404: ErrorSchema})
def create_message_api(request, thread_id: int, payload: MessageCreateSchema):
    """Create a new message within a thread."""
    try:
        thread = Thread.objects.get(id=thread_id)
        user = User.objects.get(id=payload.user_id)

        last_num = Message.objects.filter(thread=thread).aggregate(Max('message_number')).get('message_number__max') or 0
        
        metadata = {}
        if payload.role == 'user':
             metadata = {"user_id": payload.user_id, "author": payload.username, "role": user.role}
        elif payload.role == 'assistant':
             metadata = {"model": payload.model, "user_id": payload.user_id}
        else:
             metadata = {"user_id": payload.user_id}
             
        message = Message.objects.create(
            thread=thread,
            content=payload.content,
            role=payload.role,
            message_number=last_num + 1,
            metadata=metadata
        )
        return HTTPStatus.CREATED, message
    except Thread.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Thread not found."}
    except User.DoesNotExist:
         return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Message creation failed: {str(e)}"}

@api.delete("/enrollments/{enrollment_id}", response={204: None, 403: ErrorSchema, 404: ErrorSchema, 500: ErrorSchema})
def remove_student_from_course(request, enrollment_id: int, current_user_id: int):
    """
    Remove a student from a course. Only the course owner (teacher) can do this.
    A teacher cannot remove another teacher.
    `current_user_id` is passed from the client and should be the ID of the logged-in user.
    """
    try:
        enrollment = CourseEnrollment.objects.select_related('user', 'course__owner').get(id=enrollment_id)
        course_owner_id = enrollment.course.owner.id
        user_to_remove_role = enrollment.user.role

        try:
            requesting_user = User.objects.get(id=current_user_id)
            if requesting_user.role != 'teacher' or requesting_user.id != course_owner_id:
                 return HTTPStatus.FORBIDDEN, {"message": "Only the course owner (teacher) can remove participants."}
        except User.DoesNotExist:
            return HTTPStatus.BAD_REQUEST, {"message": "Requesting user not found."}

        if user_to_remove_role != 'student':
            return HTTPStatus.FORBIDDEN, {"message": "Only students can be removed. Teachers cannot remove other users who are not students."}

        enrollment.delete()
        return HTTPStatus.NO_CONTENT, None

    except CourseEnrollment.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Enrollment record not found."}
    except Exception as e:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"message": f"Failed to remove student: {str(e)}"}

# Add the thread router to the main API
api.add_router("/threads", thread_router, tags=["Threads"])

# --- Remove old Django view-based endpoints --- 
# The functions get_course_info and get_course_participants are now deprecated
# as they rely on Django sessions and aren't standard Ninja endpoints.
# They should be replaced with proper Ninja endpoints using authentication.

# Placeholder for global authentication (optional)
# class GlobalAuth(HttpBearer):
#     def authenticate(self, request, token):
#         # Implement token validation logic here if needed globally
#         # For JWT, NinjaJWTAuthController handles specific routes
#         pass

# api = NinjaAPI(auth=GlobalAuth()) # Apply auth globally if needed