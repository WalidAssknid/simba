import os
import django
import django.apps
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from .models import User, Course, Activity, Thread, Message, CourseEnrollment, ChainlitSession, InviteToken, ActivityToken
from ninja import Swagger, Router, Schema
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
    ActivityDetailSchema,
    StudentDataSchema,
    ConversationStatsSchema,
    SummaryResponseSchema,
    StudentAnalysisSchema,
    WordFrequencySchema,
    RawMessagesSchema,
    FileUploadSchema,
    ActivityFileSchema,
    ActivityFilesResponseSchema,
    ChainlitSessionInitSchema,
    ChainlitSessionResponseSchema
)
from .eventTracking import (
    accountCreated,
    createdActivity,
    closedChat,
    closedCourse,
    createdCourse,
    deletedActivity,
    deletedCourse,
    joinedActivity,
    joinedCourse,
    loggedIn,
    loggedOut,
    modifiedActivity,
    modifiedCourse,
    modifiedProfile,
    openedChat,
    openedCourse,
    sentMessage 
)
import time

from django.shortcuts import get_object_or_404
from http import HTTPStatus
from . import cluster_students
from . import openai_assistant

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
            password_hash=hashed_password
        )
        accountCreated(user,time.time())
        
        # Convert UUID to string for response
        user_data = {
            "id": str(user.id),
            "username": user.username,
            "email": user.email
        }
        return HTTPStatus.CREATED, user_data
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Registration failed: {str(e)}"}

@api.post("/auth/login", response={200: UserOutSchema, 401: ErrorSchema, 404: ErrorSchema, 500:ErrorSchema})
def login_user(request, payload: SignInSchema):
    """
    Authenticate a user and return user details.
    """
    try:
        user = User.objects.get(username=payload.username)
        if check_password(payload.password, user.password_hash):
            loggedIn(user, time.time())
            
            # Convert UUID to string for response
            user_data = {
                "id": str(user.id),
                "username": user.username,
                "email": user.email
            }
            return HTTPStatus.OK, user_data
        else:
            return HTTPStatus.UNAUTHORIZED, {"message": "Invalid credentials."}
    except User.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "User does not exist."}
    except Exception as e:
         return HTTPStatus.INTERNAL_SERVER_ERROR, {"message": f"Login failed: {str(e)}"}

@api.put("/users/{user_id}", response={200: UserOutSchema, 400: ErrorSchema, 401: ErrorSchema, 404: ErrorSchema, 409: ErrorSchema})
def update_user_profile(request, user_id: str, payload: UserUpdateSchema):
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
        modifiedProfile(user,{"username" : user.username, "email" : user.email},time.time())
        
        # Convert UUID to string for response
        user_data = {
            "id": str(user.id),
            "username": user.username,
            "email": user.email
        }
        return HTTPStatus.OK, user_data
    except User.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "User not found."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Profile update failed: {str(e)}"}

# --- Course CRUD ---
@api.post("/courses", response={201: CourseOutSchema, 400: ErrorSchema, 403: ErrorSchema})
def create_course_api(request, payload: CourseCreateSchema, user_id: str):
    """
    Create a new course. user_id is passed for now.
    Ideally, this would come from an authenticated token.
    """
    try:
        user = User.objects.get(id=user_id)
        if not user.can_create_course():
            return HTTPStatus.FORBIDDEN, {"message": "You have reached the maximum number of courses (3)."}
        
        course = Course.objects.create(
            title=payload.title,
            description=payload.description,
            owner=user
        )
        createdCourse(user,course.id,{"title" : payload.title,"description" : payload.description, "owner" : user.id},time.time())
        return HTTPStatus.CREATED, course
    except User.DoesNotExist:
        return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Course creation failed: {str(e)}"}

@api.put("/courses/{course_id}", response={200: CourseOutSchema, 400: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema})
def update_course_api(request, course_id: str, payload: CourseUpdateSchema, user_id: str):
    """
    Update an existing course. Only the owner/teacher can update it.
    """
    try:
        user = User.objects.get(id=user_id)
        course = Course.objects.get(id=course_id)
        
        if course.owner_id != user.id:
            return HTTPStatus.FORBIDDEN, {"message": "Only the course owner can update this course."}
        
        course.title = payload.title
        course.description = payload.description if payload.description else course.description
        course.save()
        modifiedCourse(user,course_id,{"title" : course.title,"description" : course.description, "owner" : user.id},time.time())
        return HTTPStatus.OK, course
    except User.DoesNotExist:
        return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except Course.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Course not found."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Course update failed: {str(e)}"}

@api.delete("/courses/{course_id}", response={204: None, 403: ErrorSchema, 404: ErrorSchema})
def delete_course_api(request, course_id: str, user_id: str):
    """
    Delete a course. Only the owner/teacher can delete it.
    """
    try:
        user = User.objects.get(id=user_id)
        course = Course.objects.get(id=course_id)
        
        if course.owner_id != user.id:
            return HTTPStatus.FORBIDDEN, {"message": "Only the course owner can delete this course."}
        
        course.delete()
        deletedCourse(user,course_id,time.time())
        return HTTPStatus.NO_CONTENT, None
    except User.DoesNotExist:
        return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except Course.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Course not found."}
    except Exception as e:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"message": f"Course deletion failed: {str(e)}"}

# --- Activity CRUD ---
@api.post("/activities", response={201: ActivityOutSchema, 400: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema})
def create_activity_api(request, payload: ActivityCreateSchema, user_id: str):
    """
    Create a new activity. user_id is passed for now.
    """
    try:
        user = User.objects.get(id=user_id)
        course = Course.objects.get(id=payload.course_id)

        # Check if user has permission to create activities in this course
        is_owner = course.owner_id == user.id
        enrollment = CourseEnrollment.objects.filter(user=user, course=course).first()
        can_create = is_owner or (enrollment and enrollment.role == 'teacher')
        
        if not can_create:
            return HTTPStatus.FORBIDDEN, {"message": "Only the course owner or teachers can create activities."}

        # Prepare activity data for OpenAI assistant
        activity_data = {
            'title': payload.title or f"Activity for {course.title}",
            'description': payload.description or '',
            'course_title': course.title,
            'expert_mode': payload.expert_mode,
            'custom_prompt': payload.custom_prompt,
            'questions': payload.questions,
            'agent_attitude': payload.agent_attitude,
            'subjects': payload.subjects,
            'restrict_to_subject': payload.restrict_to_subject,
            'allow_questions': payload.allow_questions,
            'allow_emojis': payload.allow_emojis,
            'trust_document': payload.trust_document,
            'word_limit': payload.word_limit,
            'start_date': payload.start_date,
            'end_date': payload.end_date
        }
        
        # Prepare files for upload
        files_to_upload = []
        if payload.files:
            for file_base64 in payload.files:
                try:
                    # Decode file info from base64 (assuming format: "filename:content_type:base64_content")
                    filename, content_type, content = file_base64.split(':', 2)
                    files_to_upload.append({
                        'filename': filename,
                        'content_type': content_type,
                        'content': content
                    })
                except ValueError:
                    return HTTPStatus.BAD_REQUEST, {"message": "Invalid file format. Expected 'filename:content_type:base64_content'"}
        
        # Create OpenAI assistant
        assistant_result = openai_assistant.create_assistant(activity_data, files_to_upload)
        
        if not assistant_result['success']:
            return HTTPStatus.BAD_REQUEST, {"message": f"Failed to create OpenAI assistant: {assistant_result.get('error', 'Unknown error')}"}

        activity = Activity.objects.create(
            course=course,
            owner=user,
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
            word_limit=payload.word_limit,
            start_date=payload.start_date,
            end_date=payload.end_date,
            is_visible=payload.is_visible,
            allow_redo=payload.allow_redo,
            openai_assistant_id=assistant_result['assistant_id'],
            vector_store_id=assistant_result['vector_store_id']
        )
        createdActivity(user,activity.id,{
            "course":payload.course_id,
            "owner":user_id,
            "title":activity.title,
            "description":payload.description,
            "expert_mode":payload.expert_mode,
            "custom_prompt":payload.custom_prompt,
            "questions":payload.questions,
            "agent_attitude":payload.agent_attitude,
            "subjects":payload.subjects,
            "restrict_to_subject":payload.restrict_to_subject,
            "allow_questions":payload.allow_questions,
            "allow_emojis":payload.allow_emojis,
            "trust_document":payload.trust_document,
            "word_limit":payload.word_limit,
            "start_date":payload.start_date,
            "end_date":payload.end_date,
            "is_visible":payload.is_visible,
            "allow_redo":payload.allow_redo},
            time.time())
        return HTTPStatus.CREATED, activity
    except User.DoesNotExist:
        return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except Course.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Course not found."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Activity creation failed: {str(e)}"}

@api.put("/activities/{activity_id}", response={200: ActivityOutSchema, 400: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema})
def update_activity_api(request, activity_id: str, payload: ActivityUpdateSchema, user_id: str):
    """
    Update an existing activity. Only the owner/teacher can update it.
    """
    try:
        user = User.objects.get(id=user_id)
        activity = Activity.objects.get(id=activity_id)
        
        # Check if user is the owner of the activity or the course
        if activity.owner_id != user.id and activity.course.owner_id != user.id:
            return HTTPStatus.FORBIDDEN, {"message": "Only the activity owner or course owner can update this activity."}
        
        # Update activity fields
        if payload.title is not None:
            activity.title = payload.title
        if payload.description is not None:
            activity.description = payload.description
        activity.expert_mode = payload.expert_mode
        if payload.custom_prompt is not None:
            activity.custom_prompt = payload.custom_prompt
        activity.questions = payload.questions
        activity.agent_attitude = payload.agent_attitude
        if payload.subjects is not None:
            activity.subjects = payload.subjects
        activity.restrict_to_subject = payload.restrict_to_subject
        activity.allow_questions = payload.allow_questions
        activity.allow_emojis = payload.allow_emojis
        activity.trust_document = payload.trust_document
        activity.word_limit = payload.word_limit
        if payload.start_date is not None:
            activity.start_date = payload.start_date
        if payload.end_date is not None:
            activity.end_date = payload.end_date
        activity.is_visible = payload.is_visible
        activity.allow_redo = payload.allow_redo
        
        # Handle files
        if payload.files:
            activity.files = payload.files
        
        activity.save()
        modifiedActivity(user,activity_id,{"title" : activity.title,"description" : activity.description, "owner" : user.id},time.time())
        return HTTPStatus.OK, activity
    except User.DoesNotExist:
        return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except Activity.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Activity not found."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Activity update failed: {str(e)}"}

@api.delete("/activities/{activity_id}", response={204: None, 403: ErrorSchema, 404: ErrorSchema})
def delete_activity_api(request, activity_id: str, user_id: str):
    """
    Delete an activity. Only the owner/teacher can delete it.
    """
    try:
        user = User.objects.get(id=user_id)
        activity = Activity.objects.get(id=activity_id)
        
        # Check if user is the owner of the activity or the course
        if activity.owner_id != user.id and activity.course.owner_id != user.id:
            return HTTPStatus.FORBIDDEN, {"message": "Only the activity owner or course owner can delete this activity."}
        
        activity.delete()
        deletedActivity(user,activity_id,time.time())
        return HTTPStatus.NO_CONTENT, None
    except User.DoesNotExist:
        return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except Activity.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Activity not found."}
    except Exception as e:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"message": f"Activity deletion failed: {str(e)}"}

@api.get("/activities/{activity_id}", response={200: ActivityDetailSchema, 404: ErrorSchema})
def get_activity_api(request, activity_id: str):
    """
    Get a specific activity by ID.
    """
    try:
        activity = Activity.objects.get(id=activity_id)
        
        activity_data = {
            'id': str(activity.id),
            'title': activity.title,
            'description': activity.description,
            'expert_mode': activity.expert_mode,
            'custom_prompt': activity.custom_prompt,
            'questions': activity.questions or [],
            'agent_attitude': activity.agent_attitude,
            'subjects': activity.subjects,
            'restrict_to_subject': activity.restrict_to_subject,
            'allow_questions': activity.allow_questions,
            'allow_emojis': activity.allow_emojis,
            'trust_document': activity.trust_document,
            'word_limit': activity.word_limit,
            'start_date': activity.start_date,
            'end_date': activity.end_date,
            'is_visible': activity.is_visible,
            'allow_redo': activity.allow_redo
        }
        
        return HTTPStatus.OK, activity_data
    except Activity.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Activity not found."}

# --- Thread and Message Endpoints for Chainlit --- 

thread_router = Router() 

@thread_router.post("/get-or-create", response={200: ThreadSchema, 201: ThreadSchema, 400: ErrorSchema, 404: ErrorSchema})
def get_or_create_thread_api(request, payload: ThreadGetOrCreateSchema):
    """Get an existing thread or create a new one."""
    try:
        activity = Activity.objects.get(id=payload.activity_id)
        
        latest_thread = Thread.objects.filter(
            activity=activity,
            user_id=payload.user_id
        ).order_by('-attempt_number').first()
        
        attempt_number = payload.attempt_number or 1
        
        if payload.attempt_number is None and latest_thread:
            attempt_number = latest_thread.attempt_number
        
        thread, created = Thread.objects.get_or_create(
            activity=activity,
            user_id=payload.user_id,
            attempt_number=attempt_number
        )
        
        status_code = HTTPStatus.CREATED if created else HTTPStatus.OK
        if not created:
             thread.save(update_fields=['updated_at'])

        user = User.objects.get(id=payload.user_id)
        openedChat(user,thread.id,time.time())
             
        return status_code, thread
        
    except Activity.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Activity not found."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Thread operation failed: {str(e)}"}

@thread_router.post("/new-attempt", response={201: dict, 400: ErrorSchema, 404: ErrorSchema})
def create_new_attempt_api(request, activity_id: str, user_id: str):
    """
    Create a new attempt for an activity.
    """
    try:
        user = User.objects.get(id=user_id)
        activity = Activity.objects.get(id=activity_id)
        
        # Check if the activity allows redo
        if not activity.allow_redo:
            return HTTPStatus.BAD_REQUEST, {"message": "This activity does not allow multiple attempts."}
        
        # Get the highest attempt number for this user and activity
        max_attempt = Thread.objects.filter(
            activity=activity,
            user=user
        ).aggregate(Max('attempt_number'))['attempt_number__max']
        
        new_attempt_number = (max_attempt or 0) + 1
        
        # Create a new thread for this attempt
        thread = Thread.objects.create(
            activity=activity,
            user=user,
            attempt_number=new_attempt_number
        )
        
        return HTTPStatus.CREATED, {
            "thread_id": str(thread.id),
            "attempt_number": new_attempt_number,
            "message": f"New attempt #{new_attempt_number} created successfully."
        }
    except User.DoesNotExist:
        return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except Activity.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Activity not found."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Failed to create new attempt: {str(e)}"}

@thread_router.get("/user-attempts/{activity_id}/{user_id}", response={200: dict, 400: ErrorSchema, 404: ErrorSchema})
def get_user_attempts_api(request, activity_id: str, user_id: str):
    """
    Get all attempts for a user in a specific activity.
    """
    try:
        user = User.objects.get(id=user_id)
        activity = Activity.objects.get(id=activity_id)
        
        threads = Thread.objects.filter(
            activity=activity,
            user=user
        ).order_by('attempt_number')
        
        attempts = []
        for thread in threads:
            message_count = Message.objects.filter(thread=thread).count()
            attempts.append({
                "thread_id": str(thread.id),
                "attempt_number": thread.attempt_number,
                "created_at": thread.created_at,
                "updated_at": thread.updated_at,
                "message_count": message_count
            })
        
        return HTTPStatus.OK, {
            "activity_id": str(activity_id),
            "user_id": str(user_id),
            "attempts": attempts,
            "total_attempts": len(attempts)
        }
    except User.DoesNotExist:
        return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except Activity.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Activity not found."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Failed to get attempts: {str(e)}"}

@thread_router.get("/{thread_id}/messages", response={200: List[MessageSchema], 404: ErrorSchema})
def get_messages_api(request, thread_id: str):
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
def create_message_api(request, thread_id: str, payload: MessageCreateSchema):
    """Create a new message within a thread."""
    try:
        thread = Thread.objects.get(id=thread_id)
        user = User.objects.get(id=payload.user_id)

        last_num = Message.objects.filter(thread=thread).aggregate(Max('message_number')).get('message_number__max') or 0
        
        metadata = {}
        if payload.role == 'user':
             metadata = {"user_id": str(payload.user_id), "author": payload.username}
        elif payload.role == 'assistant':
             metadata = {"model": payload.model, "user_id": str(payload.user_id)}
        else:
             metadata = {"user_id": str(payload.user_id)}
             
        message = Message.objects.create(
            thread=thread,
            content=payload.content,
            role=payload.role,
            message_number=last_num + 1,
            metadata=metadata
        )

        sentMessage(user, message.id, payload.content, time.time())
        return HTTPStatus.CREATED, message
    except Thread.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Thread not found."}
    except User.DoesNotExist:
         return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Message creation failed: {str(e)}"}

@api.delete("/enrollments/{enrollment_id}", response={204: None, 403: ErrorSchema, 404: ErrorSchema})
def remove_student_from_course(request, enrollment_id: str, current_user_id: str):
    """
    Remove a student from a course. Only course owners can do this.
    """
    try:
        current_user = User.objects.get(id=current_user_id)
        enrollment = CourseEnrollment.objects.get(id=enrollment_id)
        
        # Check if the current user is the owner of the course
        if enrollment.course.owner_id != current_user.id:
            return HTTPStatus.FORBIDDEN, {"message": "Only course owners can remove students."}
        
        # Don't allow removing the course owner
        if enrollment.user_id == enrollment.course.owner_id:
            return HTTPStatus.FORBIDDEN, {"message": "Cannot remove the course owner."}
        
        enrollment.delete()
        return HTTPStatus.NO_CONTENT, None
    except User.DoesNotExist:
        return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except CourseEnrollment.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Enrollment not found."}
    except Exception as e:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"message": f"Failed to remove student: {str(e)}"}

@api.put("/activities/{activity_id}/visibility", response={200: dict, 400: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema})
def toggle_activity_visibility_api(request, activity_id: str, user_id: str, is_visible: bool):
    """
    Toggle activity visibility. Only activity owner or course owner can do this.
    """
    try:
        user = User.objects.get(id=user_id)
        activity = Activity.objects.get(id=activity_id)
        
        # Check if user is the owner of the activity or the course
        if activity.owner_id != user.id and activity.course.owner_id != user.id:
            return HTTPStatus.FORBIDDEN, {"message": "Only the activity owner or course owner can change visibility."}
        
        activity.is_visible = is_visible
        activity.save()
        
        return HTTPStatus.OK, {
            "activity_id": str(activity_id),
            "is_visible": is_visible,
            "message": f"Activity visibility {'enabled' if is_visible else 'disabled'} successfully."
        }
    except User.DoesNotExist:
        return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except Activity.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Activity not found."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Failed to toggle visibility: {str(e)}"}

# Add the thread router to the main API
api.add_router("/threads", thread_router, tags=["Threads"])

@api.get("/courses/{course_id}", response={200: CourseOutSchema, 404: ErrorSchema})
def get_course_api(request, course_id: str):
    """
    Get a specific course by ID.
    """
    try:
        course = Course.objects.get(id=course_id)
        return HTTPStatus.OK, course
    except Course.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Course not found."}

@api.get("/courses/{course_id}/participants", response={200: dict, 404: ErrorSchema})
def get_course_participants_api(request, course_id: str):
    """
    Get all participants (students and teachers) in a course.
    """
    try:
        course = Course.objects.get(id=course_id)
        enrollments = CourseEnrollment.objects.filter(course=course).select_related('user')
        
        participants = []
        for enrollment in enrollments:
            participants.append({
                "enrollment_id": str(enrollment.id),
                "user_id": str(enrollment.user.id),
                "username": enrollment.user.username,
                "email": enrollment.user.email,
                "role": enrollment.role,
                "enrolled_at": enrollment.joined_at
            })
        
        return HTTPStatus.OK, {
            "course_id": str(course_id),
            "course_title": course.title,
            "participants": participants,
            "total_participants": len(participants)
        }
    except Course.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Course not found."}


# api = NinjaAPI(auth=GlobalAuth()) # Apply auth globally if needed

# --- Dashboard API Endpoints ---
dashboard_router = Router()


@dashboard_router.get("/student/{student_id}/", response=StudentDataSchema)
def get_student_data(request, student_id: str, course_id: str = "all", requesting_user_id: str = None):
    """
    Get comprehensive analytics data for a specific student.
    """
    try:
        student = User.objects.get(id=student_id)
        
        # Determine if this is a self-query or teacher querying student
        is_self_query = requesting_user_id is None or requesting_user_id == student_id
        
        if not is_self_query:
            # Validate permissions for teachers viewing student data
            requesting_user = User.objects.get(id=requesting_user_id)
            
            if course_id != "all":
                course = Course.objects.get(id=course_id)
                # Check if requesting user is owner or teacher in this course
                is_owner = course.owner_id == requesting_user_id
                enrollment = CourseEnrollment.objects.filter(user=requesting_user, course=course).first()
                has_permission = is_owner or (enrollment and enrollment.role == 'teacher')
                
                if not has_permission:
                    return {"error": "Permission denied. You can only view data for courses where you are owner or teacher."}
            else:
                # For "all" courses, check if requesting user has teacher/owner role in any course
                owned_courses = Course.objects.filter(owner=requesting_user)
                teacher_enrollments = CourseEnrollment.objects.filter(user=requesting_user, role='teacher')
                has_any_teacher_role = owned_courses.exists() or teacher_enrollments.exists()
                
                if not has_any_teacher_role:
                    return {"error": "Permission denied. You need teacher or owner privileges to view other students' data."}
        
        # Get courses where the student is enrolled as student
        if course_id != "all":
            course = Course.objects.get(id=course_id)
            # Check if student is enrolled in this course
            student_enrollment = CourseEnrollment.objects.filter(
                user=student, 
                course=course, 
                role='student'
            ).first()
            
            if not student_enrollment:
                return {"error": "Student is not enrolled in this course."}
                
            # Get messages from this specific course
            messages = Message.objects.filter(
                thread__user=student, 
                thread__activity__course=course,
                role='user'
            ).select_related('thread__activity').order_by('timestamp')
            
            threads = Thread.objects.filter(
                user=student,
                activity__course=course
            ).order_by('-updated_at')
            
            courses_for_comparison = [course]
        else:
            # Get all courses where student is enrolled as student
            student_courses = Course.objects.filter(
                enrollments__user=student,
                enrollments__role='student'
            )
            
            if not student_courses.exists():
                return {"error": "Student is not enrolled in any courses as a student."}
            
            messages = Message.objects.filter(
                thread__user=student,
                thread__activity__course__in=student_courses,
                role='user'
            ).select_related('thread__activity').order_by('timestamp')
            
            threads = Thread.objects.filter(
                user=student,
                activity__course__in=student_courses
            ).order_by('-updated_at')
            
            courses_for_comparison = student_courses
        
        activities = set([msg.thread.activity_id for msg in messages])
        activities_count = len(activities)
        
        messages_count = messages.count()
        total_chars = sum([len(msg.content) for msg in messages])
        
        activity_counts = {}
        for msg in messages:
            activity_name = msg.thread.activity.title or f"Activity {msg.thread.activity.id}"
            activity_counts[activity_name] = activity_counts.get(activity_name, 0) + 1
        
        conversation = []
        
        # Calculate retries based on filtered threads
        activity_attempts = {}
        for thread in threads:
            activity_id = thread.activity_id
            if activity_id not in activity_attempts:
                activity_attempts[activity_id] = []
            activity_attempts[activity_id].append(thread.attempt_number)
        
        retries_count = 0
        for activity_id, attempts in activity_attempts.items():
            retries_count += max(len(attempts) - 1, 0)
        
        # Build conversation history from filtered threads
        if threads.count() <= 5:
            for thread in threads:
                thread_messages = Message.objects.filter(thread=thread).order_by('message_number')
                conversation.extend([
                    {
                        "role": msg.role, 
                        "content": msg.content, 
                        "timestamp": msg.timestamp.isoformat(),
                        "thread_id": thread.id,
                        "activity_title": thread.activity.title or f"Activity {thread.activity.id}",
                        "message_number": msg.message_number
                    } 
                    for msg in thread_messages
                ])
        else:
            recent_thread = threads.first()
            if recent_thread:
                thread_messages = Message.objects.filter(thread=recent_thread).order_by('message_number')
                conversation = [
                    {
                        "role": msg.role, 
                        "content": msg.content, 
                        "timestamp": msg.timestamp.isoformat(),
                        "thread_id": recent_thread.id,
                        "activity_title": recent_thread.activity.title or f"Activity {recent_thread.activity.id}",
                        "message_number": msg.message_number
                    } 
                    for msg in thread_messages
                ]
        
        # For length distribution, use messages from the same courses for comparison
        all_user_messages = Message.objects.filter(
            role='user',
            thread__activity__course__in=courses_for_comparison
        )
            
        message_lengths = [len(msg.content) for msg in all_user_messages]
        student_avg_length = total_chars / messages_count if messages_count > 0 else 0
        
        max_length = max(message_lengths) if message_lengths else 1000
        bins = list(range(0, max_length + 200, 200))
        values = [0] * len(bins)
        
        for length in message_lengths:
            bin_index = min(length // 200, len(bins) - 1)
            values[bin_index] += 1
        
        return {
            "activities_count": activities_count,
            "messages_count": messages_count,
            "total_chars": total_chars,
            "messages": conversation,
            "length_distribution": {
                "bins": bins,
                "values": values
            },
            "student_length": int(student_avg_length),
            "activity_engagement": {
                "labels": list(activity_counts.keys()),
                "values": list(activity_counts.values())
            },
            "retries_count": retries_count
        }
    except User.DoesNotExist:
        return {"error": "Student not found"}
    except Course.DoesNotExist:
        return {"error": "Course not found"}
    except Exception as e:
        return {"error": str(e)}

@dashboard_router.get("/conversation_stats/", response=ConversationStatsSchema)
def get_conversation_stats(request, course_id: str = "all", requesting_user_id: str = None):
    """Get detailed conversation statistics for analysis."""
    try:
        # Validate permissions if requesting_user_id is provided
        if requesting_user_id:
            requesting_user = User.objects.get(id=requesting_user_id)
            
            if course_id != "all":
                course = Course.objects.get(id=course_id)
                # Check if requesting user is owner or teacher in this course
                is_owner = course.owner_id == requesting_user_id
                enrollment = CourseEnrollment.objects.filter(user=requesting_user, course=course).first()
                has_permission = is_owner or (enrollment and enrollment.role == 'teacher')
                
                if not has_permission:
                    return {"stats": [], "error": "Permission denied. You can only view stats for courses where you are owner or teacher."}
                    
                messages = Message.objects.filter(
                    thread__activity__course=course
                ).select_related('thread__user', 'thread__activity')
            else:
                # For "all" courses, only show data from courses where user has teacher/owner privileges
                owned_courses = Course.objects.filter(owner=requesting_user)
                teacher_courses = Course.objects.filter(
                    enrollments__user=requesting_user,
                    enrollments__role='teacher'
                )
                accessible_courses = (owned_courses | teacher_courses).distinct()
                
                if not accessible_courses.exists():
                    return {"stats": [], "error": "No courses found where you have teacher or owner privileges."}
                
                messages = Message.objects.filter(
                    thread__activity__course__in=accessible_courses
                ).select_related('thread__user', 'thread__activity')
        else:
            # No user validation - return all data (for backward compatibility)
            if course_id != "all":
                course = Course.objects.get(id=course_id)
                messages = Message.objects.filter(
                    thread__activity__course=course
                ).select_related('thread__user', 'thread__activity')
            else:
                messages = Message.objects.all().select_related('thread__user', 'thread__activity')
        
        user_stats = {}
        
        for msg in messages:
            user_id = msg.thread.user_id
            username = msg.thread.user.username
            
            if user_id not in user_stats:
                user_stats[user_id] = {
                    "username": username,
                    "total_turns": 0,
                    "user_turns": 0,
                    "model_turns": 0,
                    "total_chars": 0,
                    "activities": set(),
                    "words": set(),
                    "word_lengths": []
                }
            
            user_stats[user_id]["total_turns"] += 1
            
            if msg.role == 'user':
                user_stats[user_id]["user_turns"] += 1
                user_stats[user_id]["total_chars"] += len(msg.content)
                
                user_stats[user_id]["activities"].add(msg.thread.activity_id)
                
                words = msg.content.lower().split()
                user_stats[user_id]["words"].update(words)
                user_stats[user_id]["word_lengths"].extend([len(w) for w in words])
            else:
                user_stats[user_id]["model_turns"] += 1
        
        stats = []
        for user_id, user_data in user_stats.items():
            if user_data["model_turns"] > 0:
                turn_ratio = user_data["user_turns"] / user_data["model_turns"]
            else:
                turn_ratio = user_data["user_turns"]
                
            avg_word_length = (
                sum(user_data["word_lengths"]) / len(user_data["word_lengths"]) 
                if user_data["word_lengths"] else 0
            )
            
            stats.append({
                "username": user_data["username"],
                "total_turns": user_data["total_turns"],
                "user_turns": user_data["user_turns"],
                "model_turns": user_data["model_turns"],
                "turn_ratio": turn_ratio,
                "num_activities": len(user_data["activities"]),
                "vocab_size": len(user_data["words"]),
                "avg_word_length": avg_word_length
            })
        
        return {"stats": stats}
    except User.DoesNotExist:
        return {"stats": [], "error": "Requesting user not found"}
    except Course.DoesNotExist:
        return {"stats": [], "error": "Course not found"}
    except Exception as e:
        return {"stats": [], "error": str(e)}

@dashboard_router.get("/generate_summary/", response=SummaryResponseSchema)
def generate_activity_summary(request, activity_id: str):
    """Generate an AI summary of student conversations in an activity."""
    try:
        from openai import OpenAI
        import os
        
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return {"summary": "OpenAI API key not found. Please set the OPENAI_API_KEY environment variable."}
        
        openai_client = OpenAI(api_key=api_key)
        
        activity = Activity.objects.get(id=activity_id)
        
        messages = Message.objects.filter(
            thread__activity=activity,
            role='user'
        ).order_by('timestamp')
        
        if not messages:
            return {"summary": "No student messages found for this activity."}
        
        message_texts = [msg.content for msg in messages]
        content = "\n".join(message_texts)
        
        if len(content) > 15000:
            content = content[:15000] + "...(truncated)"
        
        prompt = f"""Based on the messages exchanged between students and SIMBA tutor, taking into consideration only the messages sent by the students:

{content}

Please provide a concise (less than 200 words) SUMMARY that:
1. Summarizes the main points discussed by the students in bullet points
2. Identifies the main difficulties or misconceptions presented by the students in bullet points
"""
        
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",  
                messages=[
                    {"role": "system", "content": "You are a teacher assistant analyzing student conversations."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500
            )
            
            summary = response.choices[0].message.content
            return {"summary": summary}
        except Exception as e:
            print(f"OpenAI API error: {str(e)}")
            return {"summary": f"Error generating summary with OpenAI: {str(e)}"}
        
    except Activity.DoesNotExist:
        return {"summary": "Activity not found."}
    except Exception as e:
        return {"summary": f"Error generating summary: {str(e)}"}

@dashboard_router.get("/generate_student_analysis/", response=StudentAnalysisSchema)
def generate_student_analysis(request, student_id: str, activity_id: str = "all"):
    """Generate an AI analysis of a student's conversation patterns."""
    try:
        from openai import OpenAI
        import os
        
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return {"analysis": "OpenAI API key not found. Please set the OPENAI_API_KEY environment variable."}
        
        openai_client = OpenAI(api_key=api_key)
        
        student = User.objects.get(id=student_id)
        
        if activity_id != "all":
            activity = Activity.objects.get(id=activity_id)
            messages = Message.objects.filter(
                thread__user=student,
                thread__activity=activity,
                role='user'
            ).order_by('timestamp')
            context = f"for activity '{activity.title}'"
        else:
            messages = Message.objects.filter(
                thread__user=student,
                role='user'
            ).order_by('timestamp')
            context = "across all activities"
        
        if not messages:
            return {"analysis": f"No data found for student {student.username} {context}."}
        
        message_texts = [msg.content for msg in messages]
        content = "\n".join(message_texts)
        
        if len(content) > 15000:
            content = content[:15000] + "...(truncated)"
        
        prompt = f"""You are a teacher assistant. Based on the messages exchanged between the student and an online tutor, here are the messages sent by the student {student.username} {context}:

{content}

Please provide a concise (less than 300 words) summary that:
1. Summarizes the main points discussed by the student.
2. Identifies the main difficulties or misconceptions presented by the student.
3. Analyzes the student's communication style, engagement level, and learning patterns.
For each point, give precise examples cited verbatim from the student's messages.
"""
        
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a teacher assistant analyzing student conversations."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=600
            )
            
            analysis = response.choices[0].message.content
            return {"analysis": analysis}
        except Exception as e:
            print(f"OpenAI API error: {str(e)}")
            return {"analysis": f"Error generating analysis with OpenAI: {str(e)}"}
        
    except User.DoesNotExist:
        return {"analysis": "Student not found."}
    except Activity.DoesNotExist:
        return {"analysis": "Activity not found."}
    except Exception as e:
        return {"analysis": f"Error generating analysis: {str(e)}"}

@dashboard_router.get("/word_frequencies/", response=WordFrequencySchema)
def get_word_frequencies(request, course_id: str = "all", min_word_length: int = 3, max_words: int = 100):
    """Get word frequencies from student messages for word cloud visualization."""
    try:
        if course_id != "all":
            course = Course.objects.get(id=course_id)
            messages = Message.objects.filter(
                thread__activity__course=course
            ).select_related('thread__user', 'thread__activity')
        else:
            messages = Message.objects.all().select_related('thread__user', 'thread__activity')
        
        print(f"DEBUG: Retrieved {messages.count()} messages for word frequency analysis")
        
        message_data = []
        for msg in messages:
            message_data.append({
                'user_id': msg.thread.user_id,
                'username': msg.thread.user.username,
                'content': msg.content,
                'role': msg.role,
                'activity_id': msg.thread.activity_id,
                'timestamp': msg.timestamp.isoformat()
            })
        
        word_frequencies = cluster_students.extract_word_frequencies(
            message_data,
            min_word_length=min_word_length,
            max_words=max_words
        )
        
        print(f"DEBUG: Extracted {len(word_frequencies['words'])} words with frequencies")
        
        return word_frequencies
    except Exception as e:
        print(f"ERROR in word_frequencies: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "words": [],
            "students": [],
            "error": str(e)
        }

@dashboard_router.get("/raw_messages/", response=RawMessagesSchema)
def get_raw_messages(request, course_id: str = "all"):
    """Get raw message data for export, with complete message content instead of truncated content."""
    try:
        if course_id != "all":
            course = Course.objects.get(id=course_id)
            messages_query = Message.objects.filter(
                thread__activity__course=course
            ).select_related('thread__user', 'thread__activity').order_by('-timestamp')
        else:
            messages_query = Message.objects.all().select_related('thread__user', 'thread__activity').order_by('-timestamp')
        
        messages = []
        for msg in messages_query:
            messages.append({
                'role': msg.role,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat(),
                'username': msg.thread.user.username,
                'activity_title': msg.thread.activity.title,
                'thread_id': msg.thread.id,
                'message_number': msg.message_number
            })
        
        return {"messages": messages}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"messages": [], "error": str(e)}

# --- Activity File Management Endpoints ---
@api.get("/activities/{activity_id}/files", response={200: ActivityFilesResponseSchema, 404: ErrorSchema, 500: ErrorSchema})
def get_activity_files_api(request, activity_id: str):
    """Get list of files for an activity."""
    try:
        activity = Activity.objects.get(id=activity_id)
        
        if not activity.vector_store_id:
            return HTTPStatus.OK, {"files": []}
        
        files = openai_assistant.get_assistant_files(activity.vector_store_id)
        return HTTPStatus.OK, {"files": files}
        
    except Activity.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Activity not found."}
    except Exception as e:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"message": f"Failed to get activity files: {str(e)}"}

@api.post("/activities/{activity_id}/files", response={201: dict, 400: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema})
def upload_activity_file_api(request, activity_id: str, payload: FileUploadSchema, user_id: str):
    """Upload a file to an activity."""
    try:
        user = User.objects.get(id=user_id)
        activity = Activity.objects.select_related('course').get(id=activity_id)
        
        # Check permissions
        is_owner = activity.course.owner_id == user.id
        enrollment = CourseEnrollment.objects.filter(user=user, course=activity.course).first()
        can_upload = is_owner or (enrollment and enrollment.role == 'teacher')
        
        if not can_upload:
            return HTTPStatus.FORBIDDEN, {"message": "Only the course owner or teachers can upload files to this activity."}
        
        if not activity.vector_store_id:
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            vector_store = client.vector_stores.create(
                name=f"Activity: {activity.title or 'Untitled'}"
            )
            activity.vector_store_id = vector_store.id
            activity.save()
        
        file_data = {
            'filename': payload.filename,
            'content_type': payload.content_type,
            'content': payload.content
        }
        
        result = openai_assistant.upload_file_to_assistant(activity.vector_store_id, file_data)
        
        if not result['success']:
            return HTTPStatus.BAD_REQUEST, {"message": f"Failed to upload file: {result.get('error', 'Unknown error')}"}
        
        return HTTPStatus.CREATED, {
            "message": "File uploaded successfully",
            "file_id": result['file_id'],
            "filename": result['filename'],
            "size": result['size']
        }
        
    except User.DoesNotExist:
        return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except Activity.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Activity not found."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"File upload failed: {str(e)}"}

@api.delete("/activities/{activity_id}/files/{file_id}", response={204: None, 403: ErrorSchema, 404: ErrorSchema, 500: ErrorSchema})
def delete_activity_file_api(request, activity_id: str, file_id: str, user_id: str):
    """Delete a file from an activity."""
    try:
        user = User.objects.get(id=user_id)
        activity = Activity.objects.select_related('course').get(id=activity_id)
        
        # Check permissions
        is_owner = activity.course.owner_id == user.id
        enrollment = CourseEnrollment.objects.filter(user=user, course=activity.course).first()
        can_delete = is_owner or (enrollment and enrollment.role == 'teacher')
        
        if not can_delete:
            return HTTPStatus.FORBIDDEN, {"message": "Only the course owner or teachers can delete files from this activity."}
        
        if not activity.vector_store_id:
            return HTTPStatus.NOT_FOUND, {"message": "No files found for this activity."}
        
        result = openai_assistant.delete_assistant_file(activity.vector_store_id, file_id)
        
        if not result['success']:
            return HTTPStatus.INTERNAL_SERVER_ERROR, {"message": f"Failed to delete file: {result.get('error', 'Unknown error')}"}
        
        return HTTPStatus.NO_CONTENT, None
        
    except User.DoesNotExist:
        return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except Activity.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Activity not found."}
    except Exception as e:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"message": f"File deletion failed: {str(e)}"}

# --- Chainlit Session Management ---
chainlit_router = Router()

# Fila temporária para sessões pendentes - armazena as sessões que estão esperando o Chainlit se conectar
PENDING_SESSIONS_QUEUE = []

@chainlit_router.post("/create-session", response={200: ChainlitSessionResponseSchema, 400: ErrorSchema, 404: ErrorSchema})
def create_chainlit_session(request, payload: ChainlitSessionInitSchema):
    """Create a Chainlit session and add it to the pending queue for Chainlit to pick up."""
    try:
        # Validate activity exists
        activity = Activity.objects.get(id=payload.activity_id)
        
        # Validate user exists
        user = User.objects.get(id=payload.user_id)
        
        # Clean up expired sessions
        from datetime import datetime, timedelta
        from django.utils import timezone
        ChainlitSession.objects.filter(expires_at__lt=timezone.now()).delete()
        
        # Check if there's already a valid session for this user/activity that's not consumed
        existing_session = ChainlitSession.objects.filter(
            user=user,
            activity=activity,
            expires_at__gt=timezone.now(),
            is_consumed=False
        ).first()
        
        if existing_session:
            # Reuse existing session - add back to queue if not already there
            session_in_queue = any(
                s.get('session_id') == existing_session.session_id 
                for s in PENDING_SESSIONS_QUEUE
            )
            if not session_in_queue:
                PENDING_SESSIONS_QUEUE.append(existing_session.session_data)
            
            return HTTPStatus.OK, existing_session.session_data
        
        # Get or create thread
        if payload.thread_id:
            # Use specific thread if provided
            thread = Thread.objects.get(id=payload.thread_id, activity=activity, user=user)
        else:
            # Get latest thread or create new one
            latest_thread = Thread.objects.filter(
                activity=activity,
                user=user
            ).order_by('-attempt_number').first()
            
            if latest_thread:
                thread = latest_thread
            else:
                # Create new thread
                thread = Thread.objects.create(
                    activity=activity,
                    user=user,
                    attempt_number=1
                )
        
        # Generate session ID (could be more sophisticated)
        import uuid
        session_id = str(uuid.uuid4())
        
        # Prepare activity data for Chainlit
        activity_data = {
            'id': str(activity.id),
            'title': activity.title,
            'description': activity.description,
            'expert_mode': activity.expert_mode,
            'custom_prompt': activity.custom_prompt,
            'questions': activity.questions,
            'agent_attitude': activity.agent_attitude,
            'subjects': activity.subjects,
            'restrict_to_subject': activity.restrict_to_subject,
            'allow_questions': activity.allow_questions,
            'allow_emojis': activity.allow_emojis,
            'trust_document': activity.trust_document,
            'word_limit': activity.word_limit,
            'openai_assistant_id': activity.openai_assistant_id,
            'vector_store_id': activity.vector_store_id,
            'course': {
                'id': str(activity.course.id),
                'title': activity.course.title
            }
        }
        
        # Prepare session data
        session_data = {
            'session_id': session_id,
            'activity_id': str(activity.id),
            'user_id': str(user.id),
            'username': payload.username,
            'thread_id': str(thread.id),
            'activity_data': activity_data
        }
        
        # Store session data in database with expiration (1 hour)
        expires_at = timezone.now() + timedelta(hours=1)
        
        chainlit_session = ChainlitSession.objects.create(
            session_id=session_id,
            activity=activity,
            user=user,
            thread=thread,
            username=payload.username,
            session_data=session_data,
            expires_at=expires_at,
            is_consumed=False
        )
        
        # Add to pending sessions queue for Chainlit to pick up
        PENDING_SESSIONS_QUEUE.append(session_data)
        
        # Track event
        openedChat(user, thread.id, time.time())
        
        # Return session data without session_id for frontend use
        return HTTPStatus.OK, session_data
        
    except Activity.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Activity not found."}
    except User.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "User not found."}
    except Thread.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Thread not found."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Failed to create session: {str(e)}"}

@chainlit_router.get("/next-session", response={200: ChainlitSessionResponseSchema, 404: ErrorSchema})
def get_next_chainlit_session(request):
    """Get the next session from the pending queue or database for Chainlit to process."""
    try:
        # First, try to get from the in-memory queue (fastest)
        if PENDING_SESSIONS_QUEUE:
            session_data = PENDING_SESSIONS_QUEUE.pop(0)
            return HTTPStatus.OK, session_data
        
        # If queue is empty, try to find a valid session in the database
        from django.utils import timezone
        
        # Look for unexpired sessions in the database
        valid_session = ChainlitSession.objects.filter(
            expires_at__gt=timezone.now(),
            is_consumed=False
        ).select_related('activity', 'user', 'thread').first()
        
        if valid_session:
            # Mark session as consumed to prevent reuse
            valid_session.is_consumed = True
            valid_session.save()
            
            # Return the stored session data
            return HTTPStatus.OK, valid_session.session_data
        else:
            return HTTPStatus.NOT_FOUND, {"message": "No pending sessions."}
            
    except Exception as e:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"message": f"Failed to get next session: {str(e)}"}

@chainlit_router.post("/init-session", response={200: ChainlitSessionResponseSchema, 400: ErrorSchema, 404: ErrorSchema})
def init_chainlit_session(request, payload: ChainlitSessionInitSchema):
    """Initialize a Chainlit session with the provided parameters (legacy method)."""
    try:
        # Validate activity exists
        activity = Activity.objects.get(id=payload.activity_id)
        
        # Validate user exists
        user = User.objects.get(id=payload.user_id)
        
        # Get or create thread
        if payload.thread_id:
            # Use specific thread if provided
            thread = Thread.objects.get(id=payload.thread_id, activity=activity, user=user)
        else:
            # Get latest thread or create new one
            latest_thread = Thread.objects.filter(
                activity=activity,
                user=user
            ).order_by('-attempt_number').first()
            
            if latest_thread:
                thread = latest_thread
            else:
                # Create new thread
                thread = Thread.objects.create(
                    activity=activity,
                    user=user,
                    attempt_number=1
                )
        
        # Generate session ID (could be more sophisticated)
        import uuid
        session_id = str(uuid.uuid4())
        
        # Prepare activity data for Chainlit
        activity_data = {
            'id': str(activity.id),
            'title': activity.title,
            'description': activity.description,
            'expert_mode': activity.expert_mode,
            'custom_prompt': activity.custom_prompt,
            'questions': activity.questions,
            'agent_attitude': activity.agent_attitude,
            'subjects': activity.subjects,
            'restrict_to_subject': activity.restrict_to_subject,
            'allow_questions': activity.allow_questions,
            'allow_emojis': activity.allow_emojis,
            'trust_document': activity.trust_document,
            'word_limit': activity.word_limit,
            'openai_assistant_id': activity.openai_assistant_id,
            'vector_store_id': activity.vector_store_id,
            'course': {
                'id': str(activity.course.id),
                'title': activity.course.title
            }
        }
        
        # Prepare session data
        session_data = {
            'session_id': session_id,
            'activity_id': str(activity.id),
            'user_id': str(user.id),
            'username': payload.username,
            'thread_id': str(thread.id),
            'activity_data': activity_data
        }
        
        # Store session data in database with expiration (1 hour)
        from datetime import datetime, timedelta
        from django.utils import timezone
        expires_at = timezone.now() + timedelta(hours=1)
        
        # Delete any existing session for this user/activity to avoid duplicates
        ChainlitSession.objects.filter(
            user=user,
            activity=activity,
            expires_at__lt=timezone.now()
        ).delete()
        
        chainlit_session = ChainlitSession.objects.create(
            session_id=session_id,
            activity=activity,
            user=user,
            thread=thread,
            username=payload.username,
            session_data=session_data,
            expires_at=expires_at
        )
        
        # Track event
        openedChat(user, thread.id, time.time())
        
        return HTTPStatus.OK, session_data
        
    except Activity.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Activity not found."}
    except User.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "User not found."}
    except Thread.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Thread not found."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Failed to initialize session: {str(e)}"}

@chainlit_router.get("/session/{session_id}", response={200: ChainlitSessionResponseSchema, 404: ErrorSchema})
def get_chainlit_session(request, session_id: str):
    """Get session data by session ID."""
    try:
        from django.utils import timezone
        
        # Clean up expired sessions
        ChainlitSession.objects.filter(expires_at__lt=timezone.now()).delete()
        
        # Get session
        chainlit_session = ChainlitSession.objects.get(
            session_id=session_id,
            expires_at__gt=timezone.now()
        )
        
        return HTTPStatus.OK, chainlit_session.session_data
        
    except ChainlitSession.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Session not found or expired. Please re-initialize."}
    except Exception as e:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"message": f"Failed to get session: {str(e)}"}

api.add_router("/chainlit", chainlit_router, tags=["Chainlit"])
api.add_router("/dashboard", dashboard_router, tags=["Dashboard"])

@api.post("/courses/{course_id}/invite-tokens", response={201: dict, 403: ErrorSchema, 404: ErrorSchema, 500: ErrorSchema})
def generate_invite_token(request, course_id: str, role: str):
    """
    Generate an invite token for a course. Only course owners can generate tokens.
    """
    try:
        user_id = request.session.get('user_id')
        if not user_id:
            return HTTPStatus.UNAUTHORIZED, {"message": "Authentication required."}
        
        course = Course.objects.select_related('owner').get(id=course_id)
        user = User.objects.get(id=user_id)
        
        # Only course owner can generate invite tokens
        if course.owner.id != user.id:
            return HTTPStatus.FORBIDDEN, {"message": "Only course owners can generate invite tokens."}
        
        # Validate role
        if role not in ['student', 'teacher']:
            return HTTPStatus.BAD_REQUEST, {"message": "Invalid role. Must be 'student' or 'teacher'."}
        
        # Check if there's already a valid token for this course and role
        existing_token = InviteToken.objects.filter(
            course=course, 
            role=role, 
            is_active=True,
            expires_at__gt=timezone.now()
        ).first()
        
        if existing_token:
            # Return the existing valid token instead of creating a new one
            invite_url = f"{request.build_absolute_uri('/').rstrip('/')}/courses/invite/{existing_token.token}"
            return HTTPStatus.CREATED, {
                "token": existing_token.token,
                "invite_url": invite_url,
                "role": role,
                "expires_at": existing_token.expires_at.isoformat()
            }
        
        # Create new token only if no valid one exists
        invite_token = InviteToken.objects.create(
            course=course,
            role=role,
            created_by=user
        )
        
        # Generate the invite URL
        invite_url = f"{request.build_absolute_uri('/').rstrip('/')}/courses/invite/{invite_token.token}"
        
        return HTTPStatus.CREATED, {
            "token": invite_token.token,
            "invite_url": invite_url,
            "role": role,
            "expires_at": invite_token.expires_at.isoformat()
        }
        
    except Course.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Course not found."}
    except User.DoesNotExist:
        return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except Exception as e:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"message": f"Failed to generate invite token: {str(e)}"}

@api.post("/activities/{activity_id}/activity-tokens", response={201: dict, 403: ErrorSchema, 404: ErrorSchema, 500: ErrorSchema})
def generate_activity_token(request, activity_id: str):
    """
    Generate an activity token for direct access to an activity. 
    Only activity owners or course owners can generate tokens.
    """
    try:
        user_id = request.session.get('user_id')
        if not user_id:
            return HTTPStatus.UNAUTHORIZED, {"message": "Authentication required."}
        
        activity = Activity.objects.select_related('course', 'owner').get(id=activity_id)
        user = User.objects.get(id=user_id)
        
        # Only activity owner or course owner can generate activity tokens
        if activity.owner.id != user.id and activity.course.owner.id != user.id:
            return HTTPStatus.FORBIDDEN, {"message": "Only activity or course owners can generate activity tokens."}
        
        # Check if there's already a valid token for this activity
        existing_token = ActivityToken.objects.filter(
            activity=activity, 
            is_active=True,
            expires_at__gt=timezone.now()
        ).first()
        
        if existing_token:
            # Return the existing valid token instead of creating a new one
            activity_url = f"{request.build_absolute_uri('/').rstrip('/')}/activities/join/{existing_token.token}"
            return HTTPStatus.CREATED, {
                "token": existing_token.token,
                "activity_url": activity_url,
                "activity_title": activity.title,
                "course_title": activity.course.title,
                "expires_at": existing_token.expires_at.isoformat()
            }
        
        # Create new token only if no valid one exists
        activity_token = ActivityToken.objects.create(
            activity=activity,
            created_by=user
        )
        
        # Generate the activity URL
        activity_url = f"{request.build_absolute_uri('/').rstrip('/')}/activities/join/{activity_token.token}"
        
        return HTTPStatus.CREATED, {
            "token": activity_token.token,
            "activity_url": activity_url,
            "activity_title": activity.title,
            "course_title": activity.course.title,
            "expires_at": activity_token.expires_at.isoformat()
        }
        
    except Activity.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Activity not found."}
    except User.DoesNotExist:
        return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except Exception as e:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"message": f"Failed to generate activity token: {str(e)}"}