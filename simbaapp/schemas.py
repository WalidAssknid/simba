from ninja import ModelSchema, Schema
from .models import (
    User,
    Institution,
    UserInstitution,
    Classroom,
    ClassEnrollment,
    Topic,
    Activity,
    Message,
    Analytics
)

class SignInSchema(Schema):
    email: str
    password: str

class InstitutionSchema(ModelSchema):
    class Config:
        model = Institution
        model_fields = "__all__"

class UserSchema(ModelSchema):
    class Config:
        model = User
        model_fields = "__all__"

class UserInstitutionSchema(ModelSchema):
    class Config:
        model = UserInstitution
        model_fields = "__all__"

class ClassroomSchema(ModelSchema):
    class Config:
        model = Classroom
        model_fields = "__all__"

class ClassEnrollmentSchema(ModelSchema):
    class Config:
        model = ClassEnrollment
        model_fields = "__all__"

class TopicSchema(ModelSchema):
    class Config:
        model = Topic
        model_fields = "__all__"

class ActivitySchema(ModelSchema):
    class Config:
        model = Activity
        model_fields = "__all__"


class MessageSchema(ModelSchema):
    class Config:
        model = Message
        model_fields = "__all__"

class AnalyticsSchema(ModelSchema):
    class Config:
        model = Analytics
        model_fields = "__all__"

