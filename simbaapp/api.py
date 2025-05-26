import os
import django
import django.apps
from django.contrib.auth.hashers import make_password, check_password
from .models import User, Course, Activity, Thread, Message, CourseEnrollment
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
    ClusterResponseSchema,
    WordFrequencySchema,
    RawMessagesSchema
)
import eventTracking as et
import time

from django.shortcuts import get_object_or_404
from http import HTTPStatus
from . import cluster_students

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
        et.accountCreated(user.id,time.time())
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
            et.loggedIn(user.id, time.time())
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
        et.modifiedProfile(user.id,{"username" : user.username, "email" : user.email},time.time())
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
        et.createdCourse(user_id,course.id,{"title" : payload.title,"description" : payload.description, "owner" : user.id},time.time())
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
        et.modifiedCourse(user_id,course_id,{"title" : course.title,"description" : course.description, "owner" : user.id},time.time())
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
        et.deletedCourse(user_id,course_id,time.time())
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
            word_limit=payload.word_limit,
            start_date=payload.start_date,
            end_date=payload.end_date,
            is_visible=payload.is_visible,
            allow_redo=payload.allow_redo
        )
        et.createdActivity(user_id,activity.id,{"course":payload.course_id,
            "user":user_id,
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
            "word_limit":payload.word_limit},
            time.time())
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
        
        if activity.course.owner_id != user.id or user.role != 'teacher':
            return HTTPStatus.FORBIDDEN, {"message": "Only the course owner can update this activity."}
        
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
        activity.start_date = payload.start_date
        activity.end_date = payload.end_date
        activity.is_visible = payload.is_visible
        activity.allow_redo = payload.allow_redo
        
        activity.save()
        et.modifiedActivity(user_id,activity_id,{"course":activity.course,
            "user":user_id,
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
            "word_limit":payload.word_limit},
            time.time())
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
        
        if activity.course.owner_id != user.id or user.role != 'teacher':
            return HTTPStatus.FORBIDDEN, {"message": "Only the course owner can delete this activity."}
        
        activity.delete()
        et.deletedActivity(user_id,activity_id,time.time())
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
             
        return status_code, thread
        
    except Activity.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Activity not found."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Thread operation failed: {str(e)}"}

@thread_router.post("/new-attempt", response={201: ThreadSchema, 400: ErrorSchema, 404: ErrorSchema})
def create_new_attempt_api(request, activity_id: int, user_id: int):
    """Create a new attempt for an activity."""
    try:
        activity = Activity.objects.get(id=activity_id)
        
        if not activity.allow_redo:
            return HTTPStatus.BAD_REQUEST, {"message": "This activity does not allow redo attempts."}
        
        latest_thread = Thread.objects.filter(
            activity=activity,
            user_id=user_id
        ).order_by('-attempt_number').first()
        
        new_attempt_number = (latest_thread.attempt_number + 1) if latest_thread else 1
        
        thread = Thread.objects.create(
            activity=activity,
            user_id=user_id,
            attempt_number=new_attempt_number
        )
        
        return HTTPStatus.CREATED, thread
        
    except Activity.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Activity not found."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Failed to create new attempt: {str(e)}"}

@thread_router.get("/user-attempts/{activity_id}/{user_id}", response={200: List[ThreadSchema], 404: ErrorSchema})
def get_user_attempts_api(request, activity_id: int, user_id: int):
    """Get all attempts for a user on a specific activity."""
    try:
        activity = Activity.objects.get(id=activity_id)
        threads = Thread.objects.filter(
            activity=activity,
            user_id=user_id
        ).order_by('-attempt_number')
        
        return HTTPStatus.OK, list(threads)
        
    except Activity.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Activity not found."}
    except Exception as e:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"message": f"Failed to get user attempts: {str(e)}"}

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

@api.put("/activities/{activity_id}/visibility", response={200: ActivityOutSchema, 400: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema})
def toggle_activity_visibility_api(request, activity_id: int, user_id: int, is_visible: bool):
    """Toggle activity visibility for students."""
    try:
        user = User.objects.get(id=user_id)
        activity = Activity.objects.select_related('course').get(id=activity_id)
        
        if activity.course.owner_id != user.id or user.role != 'teacher':
            return HTTPStatus.FORBIDDEN, {"message": "Only the course owner can change activity visibility."}
        
        activity.is_visible = is_visible
        activity.save(update_fields=['is_visible'])
        
        return HTTPStatus.OK, activity
    except User.DoesNotExist:
        return HTTPStatus.BAD_REQUEST, {"message": "Invalid user ID."}
    except Activity.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Activity not found."}
    except Exception as e:
        return HTTPStatus.BAD_REQUEST, {"message": f"Failed to update activity visibility: {str(e)}"}

# Add the thread router to the main API
api.add_router("/threads", thread_router, tags=["Threads"])

@api.get("/courses/{course_id}", response={200: CourseOutSchema, 404: ErrorSchema})
def get_course_api(request, course_id: int):
    """Fetch details for a specific course."""
    try:
        course = Course.objects.get(id=course_id)
        return HTTPStatus.OK, course
    except Course.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Course not found."}
    except Exception as e:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"message": f"Failed to get course: {str(e)}"}

@api.get("/courses/{course_id}/participants", response={200: dict, 404: ErrorSchema, 500: ErrorSchema})
def get_course_participants_api(request, course_id: int):
    """Fetch all participants for a specific course."""
    try:
        course = Course.objects.get(id=course_id)
        enrollments = CourseEnrollment.objects.filter(course_id=course_id).select_related('user')
        participants = []
        
        owner_data = {
            "id": course.owner.id,
            "username": course.owner.username,
            "role": course.owner.role,
            "is_owner": True,
            "enrollment_id": None
        }
        participants.append(owner_data)
        
        for enrollment in enrollments:
            if enrollment.user.id != course.owner.id:  
                participant_data = {
                    "id": enrollment.user.id,
                    "username": enrollment.user.username,
                    "role": enrollment.user.role,
                    "is_owner": False,
                    "enrollment_id": enrollment.id
                }
                participants.append(participant_data)
        
        return HTTPStatus.OK, {"participants": participants, "owner_id": course.owner.id}
    except Course.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "Course not found."}
    except Exception as e:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"message": f"Failed to get participants: {str(e)}"}


# api = NinjaAPI(auth=GlobalAuth()) # Apply auth globally if needed

# --- Dashboard API Endpoints ---
dashboard_router = Router()


@dashboard_router.get("/student/{student_id}/", response=StudentDataSchema)
def get_student_data(request, student_id: int, course_id: str = "all"):
    """Get detailed data for a specific student."""
    try:
        student = User.objects.get(id=student_id)
        
        if course_id != "all":
            course = Course.objects.get(id=course_id)
            messages = Message.objects.filter(
                thread__user=student, 
                thread__activity__course=course,
                role='user'
            ).select_related('thread__activity').order_by('timestamp')
        else:
            messages = Message.objects.filter(
                thread__user=student,
                role='user'
            ).select_related('thread__activity').order_by('timestamp')
        
        activities = set([msg.thread.activity_id for msg in messages])
        activities_count = len(activities)
        
        messages_count = messages.count()
        total_chars = sum([len(msg.content) for msg in messages])
        
        activity_counts = {}
        for msg in messages:
            activity_name = msg.thread.activity.title or f"Activity {msg.thread.activity.id}"
            activity_counts[activity_name] = activity_counts.get(activity_name, 0) + 1
        
        threads = Thread.objects.filter(user=student).order_by('-updated_at')
        conversation = []
        
        activity_attempts = {}
        for thread in threads:
            activity_id = thread.activity_id
            if activity_id not in activity_attempts:
                activity_attempts[activity_id] = []
            activity_attempts[activity_id].append(thread.attempt_number)
        
        retries_count = 0
        for activity_id, attempts in activity_attempts.items():
            retries_count += max(len(attempts) - 1, 0)
        
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
        
        all_user_messages = Message.objects.filter(role='user')
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
    except Exception as e:
        return {"error": str(e)}

@dashboard_router.get("/conversation_stats/", response=ConversationStatsSchema)
def get_conversation_stats(request, course_id: str = "all"):
    """Get detailed conversation statistics for analysis."""
    try:
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
    except Exception as e:
        return {"stats": [], "error": str(e)}

@dashboard_router.get("/generate_summary/", response=SummaryResponseSchema)
def generate_activity_summary(request, activity_id: int):
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
def generate_student_analysis(request, student_id: int, activity_id: str = "all"):
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

@dashboard_router.get("/student_clusters/", response=ClusterResponseSchema)
def get_student_clusters(request, course_id: str = "all", n_clusters: int = 3):
    """Get student clusters based on conversation patterns."""
    try:
        if course_id != "all":
            course = Course.objects.get(id=course_id)
            messages = Message.objects.filter(
                thread__activity__course=course
            ).select_related('thread__user', 'thread__activity')
        else:
            messages = Message.objects.all().select_related('thread__user', 'thread__activity')
        
        print(f"DEBUG: Retrieved {messages.count()} messages for clustering")
        
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
        
        print(f"DEBUG: Converted {len(message_data)} messages to clustering format")
        
        user_features = cluster_students.extract_features(message_data)
        
        print(f"DEBUG: Extracted features for {len(user_features)} users")
        if not user_features.empty:
            print(f"DEBUG: User features columns: {user_features.columns.tolist()}")
            print(f"DEBUG: First user features: {user_features.iloc[0].to_dict() if len(user_features) > 0 else 'No users'}")
        
        if user_features.empty:
            print("DEBUG: No user features extracted, returning empty result")
            return {
                "clusters": [],
                "features": []
            }
        
        n_clusters = min(n_clusters, len(user_features))
        if n_clusters < 2:
            n_clusters = 2
            
        print(f"DEBUG: Running clustering with n_clusters={n_clusters}")
        clustered_features = cluster_students.run_clustering(
            user_features, 
            n_clusters=n_clusters
        )
        
        try:
            cluster_names = cluster_students.get_cluster_names(clustered_features)
            print(f"DEBUG: Generated cluster names: {cluster_names}")
        except Exception as e:
            print(f"ERROR in generating cluster names: {str(e)}")
            cluster_names = {
                cluster_id: f"Cluster {cluster_id}" 
                for cluster_id in clustered_features['cluster'].unique()
            }
        
        clusters = []
        for cluster_id in sorted(clustered_features['cluster'].unique()):
            cluster_users = clustered_features[clustered_features['cluster'] == cluster_id]
            clusters.append({
                'id': int(cluster_id),
                'name': cluster_names.get(cluster_id, f"Cluster {cluster_id}"),
                'size': len(cluster_users),
                'users': cluster_users[['user_id', 'username']].to_dict('records')
            })
        
        features_to_return = [
            'user_id', 'username', 'num_messages', 'avg_length',
            'vocab_size', 'lexical_diversity', 'cluster'
        ]
        available_features = [f for f in features_to_return if f in clustered_features.columns]
        
        feature_data = clustered_features[available_features].to_dict('records')
        
        print(f"DEBUG: Returning {len(clusters)} clusters with {len(feature_data)} user features")
        
        return {
            "clusters": clusters,
            "features": feature_data
        }
    except Exception as e:
        print(f"ERROR in student_clusters: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "clusters": [],
            "features": [],
            "error": str(e)
        }

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

api.add_router("/dashboard", dashboard_router, tags=["Dashboard"])