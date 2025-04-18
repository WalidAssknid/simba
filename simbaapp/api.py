from django.contrib.auth.hashers import make_password, check_password
from pydantic import BaseModel, EmailStr, Field
from .models import User
from ninja import Swagger, Schema
from ninja_extra import NinjaExtraAPI
from ninja_jwt.controller import NinjaJWTDefaultController
from .schemas import UserSchema, SignInSchema

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