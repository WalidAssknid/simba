from ninja import ModelSchema, Schema
from pydantic import EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from .models import (
    User,
    Course,
    Activity,
    Message,
    Thread,
    Analytics
)

# --- Authentication Schemas ---

class SignInSchema(Schema):
    username: str
    password: str

class UserRegisterSchema(Schema):
    username: str
    email: EmailStr
    password: str
    password_confirm: str

class UserUpdateSchema(Schema):
    username: str
    email: EmailStr
    current_password: str
    new_password: Optional[str] = None
    new_password_confirm: Optional[str] = None

# --- Input Schemas ---

class CourseCreateSchema(Schema):
    title: str
    description: Optional[str] = None

class CourseUpdateSchema(Schema):
    title: str
    description: Optional[str] = None

class CourseEnrollmentSchema(Schema):
    enrollment_code: str
    role: str = 'student' 

class ActivityCreateSchema(Schema):
    course_id: int 
    title: Optional[str] = None
    description: Optional[str] = None
    expert_mode: bool = False
    custom_prompt: Optional[str] = None
    questions: List[str] = Field(default_factory=list)
    agent_attitude: str = 'friendly'
    subjects: Optional[str] = None
    restrict_to_subject: bool = False
    allow_questions: bool = True
    allow_emojis: bool = True
    trust_document: bool = True
    word_limit: int = 0
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_visible: bool = True
    allow_redo: bool = True
    files: List[str] = Field(default_factory=list)  

class ActivityUpdateSchema(Schema):
    title: Optional[str] = None
    description: Optional[str] = None
    expert_mode: bool = False
    custom_prompt: Optional[str] = None
    questions: List[str] = Field(default_factory=list)
    agent_attitude: str = 'friendly'
    subjects: Optional[str] = None
    restrict_to_subject: bool = False
    allow_questions: bool = True
    allow_emojis: bool = True
    trust_document: bool = True
    word_limit: int = 0
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_visible: bool = True
    allow_redo: bool = True
    files: List[str] = Field(default_factory=list) 

class ThreadGetOrCreateSchema(Schema):
    activity_id: int
    user_id: int
    attempt_number: Optional[int] = 1

class MessageCreateSchema(Schema):
    thread_id: int
    content: str
    role: str
    user_id: int
    username: Optional[str] = None 
    model: Optional[str] = None

# --- Output Schemas ---

class UserOutSchema(Schema):
    id: int
    username: str
    email: str

class ErrorSchema(Schema):
    message: str

class CourseOutSchema(ModelSchema):
    class Config:
        model = Course
        model_fields = ["id", "title", "description", "owner", "created_at", "enrollment_code"]

class ActivityOutSchema(ModelSchema):
    class Meta:
        model = Activity
        fields = "__all__"

class ActivityDetailSchema(ModelSchema):
    id: int
    title: Optional[str]
    description: Optional[str]
    expert_mode: bool
    custom_prompt: Optional[str]
    questions: List[str] 
    agent_attitude: str
    subjects: Optional[str]
    restrict_to_subject: bool
    allow_questions: bool
    allow_emojis: bool
    trust_document: bool
    word_limit: int
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    is_visible: bool
    allow_redo: bool

    class Meta:
        model = Activity
        fields = [
            "id",
            "title",
            "description",
            "expert_mode",
            "custom_prompt",
            "questions",
            "agent_attitude",
            "subjects",
            "restrict_to_subject",
            "allow_questions",
            "allow_emojis",
            "trust_document",
            "word_limit",
            "start_date",
            "end_date",
            "is_visible",
            "allow_redo"
        ]

class ThreadSchema(ModelSchema):
    class Meta:
        model = Thread
        fields = ["id", "activity", "user", "created_at", "updated_at", "attempt_number"]

class MessageSchema(ModelSchema):
    class Meta:
        model = Message
        fields = ["id", "content", "role", "timestamp", "metadata", "message_number"]
    
    metadata: Optional[Dict[str, Any]] = None 
    timestamp: datetime

# --- Model Schemas ---

class UserSchema(ModelSchema):
    class Config:
        model = User
        model_fields = "__all__"

class CourseSchema(ModelSchema):
    class Config:
        model = Course
        model_fields = ["id", "title", "description", "owner", "created_at", "enrollment_code"]

class ActivitySchema(ModelSchema):
    class Config:
        model = Activity
        model_fields = "__all__"

class AnalyticsSchema(ModelSchema):
    class Config:
        model = Analytics
        model_fields = "__all__"


class StudentDataSchema(Schema):
    activities_count: int
    messages_count: int
    total_chars: int
    messages: list
    length_distribution: dict
    student_length: int
    activity_engagement: dict
    retries_count: int

class ConversationStatsSchema(Schema):
    stats: list

class SummaryResponseSchema(Schema):
    summary: str

class StudentAnalysisSchema(Schema):
    analysis: str

class ClusterResponseSchema(Schema):
    clusters: list
    features: list

class WordFrequencySchema(Schema):
    words: list
    students: list

class RawMessagesSchema(Schema):
    messages: list

class FileUploadSchema(Schema):
    filename: str
    content: str 
    content_type: str

class ActivityFileSchema(Schema):
    id: str
    filename: str
    size: int
    created_at: datetime

class ActivityFilesResponseSchema(Schema):
    files: List[ActivityFileSchema]
