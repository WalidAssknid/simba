from django.contrib.auth.hashers import make_password, check_password
from pydantic import BaseModel, EmailStr, Field
from .models import User, Course, CourseEnrollment
from ninja import Swagger, Schema
from ninja_extra import NinjaExtraAPI
from ninja_jwt.controller import NinjaJWTDefaultController
from .schemas import UserSchema, SignInSchema
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

api = NinjaExtraAPI(csrf=False, docs=Swagger(settings={"persistAuthorization": True}))
api.register_controllers(NinjaJWTDefaultController)

class UserRegisterSchema(Schema):
    username: str
    email: EmailStr
    password: str
    password_confirm: str

class UserLoginSchema(Schema):
    username: str
    password: str

@api.post("/register", response=UserSchema)
def register(request, payload: UserRegisterSchema):
    if payload.password != payload.password_confirm:
        return api.create_response(request, {"error": "Passwords do not match"}, status=400)
    if User.objects.filter(username=payload.username).exists():
        return api.create_response(request, {"error": "Username already exists"}, status=400)
    if User.objects.filter(email=payload.email).exists():
        return api.create_response(request, {"error": "Email already registered"}, status=400)
    hashed_password = make_password(payload.password)
    user = User.objects.create(
        username=payload.username,
        email=payload.email,
        password_hash=hashed_password
    )
    return user

@api.post("/login")
def login(request, payload: SignInSchema):
    try:
        user = User.objects.get(username=payload.username)
    except User.DoesNotExist:
        return api.create_response(request, {"error": "Invalid credentials"}, status=400)
    
    if not check_password(payload.password, user.password_hash):
        return api.create_response(request, {"error": "Invalid credentials"}, status=400)
    
    return {
        "message": "Login successful",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role
        }
    }

def get_course_info(request, course_id):
    """API endpoint to get course information including enrollment code"""
    if not request.session.get('user_id'):
        return JsonResponse({"error": "Not authenticated"}, status=401)
    
    user_id = request.session.get('user_id')
    user = User.objects.get(id=user_id)
    course = get_object_or_404(Course, id=course_id)
    
    # Check if user has access to the course
    has_access = False
    if course.owner_id == user_id:
        has_access = True
    elif CourseEnrollment.objects.filter(user=user, course=course).exists():
        has_access = True
    
    if not has_access:
        return JsonResponse({"error": "Access denied"}, status=403)
    
    # Return enrollment code only for teachers/owners
    if course.owner_id == user_id:
        return JsonResponse({
            "id": course.id,
            "title": course.title,
            "enrollment_code": course.enrollment_code,
            "owner": course.owner.username
        })
    else:
        return JsonResponse({
            "id": course.id,
            "title": course.title,
            "owner": course.owner.username
        })

def get_course_participants(request, course_id):
    """API endpoint to get course participants"""
    if not request.session.get('user_id'):
        return JsonResponse({"error": "Not authenticated"}, status=401)
    
    user_id = request.session.get('user_id')
    user = User.objects.get(id=user_id)
    course = get_object_or_404(Course, id=course_id)
    
    # Check if user has access to the course
    has_access = False
    if course.owner_id == user_id:
        has_access = True
    elif CourseEnrollment.objects.filter(user=user, course=course).exists():
        has_access = True
    
    if not has_access:
        return JsonResponse({"error": "Access denied"}, status=403)
    
    # Get all participants
    enrollments = CourseEnrollment.objects.filter(course=course).select_related('user')
    participants = [{
        "username": enrollment.user.username,
        "role": enrollment.user.role,
        "id": enrollment.user.id
    } for enrollment in enrollments]
    
    # Add owner if not already in the list
    owner_ids = [p["id"] for p in participants]
    if course.owner.id not in owner_ids:
        participants.append({
            "username": course.owner.username,
            "role": "teacher (owner)",
            "id": course.owner.id
        })
    
    return JsonResponse({
        "course_id": course.id,
        "course_title": course.title,
        "participants": participants
    })