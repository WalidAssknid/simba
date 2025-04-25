import os
import django
from openai import AsyncOpenAI
import chainlit as cl
import logging
import urllib.parse
from asgiref.sync import sync_to_async
from django.db.models import Max

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'simba.settings')
django.setup()

from simbaapp.models import Activity, Message, Thread, User

# OpenAI client
client = AsyncOpenAI()

settings = {
    "model": "gpt-4o-mini",
    "temperature": 0.7,
}

# --- ASYNC DB HELPERS ---
@sync_to_async
def get_activity_by_id(activity_id):
    return Activity.objects.get(id=activity_id)


@sync_to_async
def get_course_from_activity(activity):
    return activity.course

@sync_to_async
def get_course_title(activity):
    return activity.course.title

@sync_to_async
def get_activity_title(activity):
    return activity.title

@sync_to_async
def get_user_by_id(user_id):
    return User.objects.get(id=user_id)

@sync_to_async
def create_user_message(thread, content, user_id, username):
    user = User.objects.get(id=user_id)
    last_num = Message.objects.filter(thread=thread).aggregate(Max('message_number')).get('message_number__max') or 0
    return Message.objects.create(
        thread=thread,
        content=content,
        role=user.role,  
        message_number=last_num + 1,
        metadata={
            "user_id": user_id,
            "author": username,
            "role": user.role
        }
    )

@sync_to_async
def create_assistant_message(thread, content, model, user_id):
    last_num = Message.objects.filter(thread=thread).aggregate(Max('message_number')).get('message_number__max') or 0
    return Message.objects.create(
        thread=thread,
        content=content,
        role="assistant",
        message_number=last_num + 1,
        metadata={
            "model": model,
            "user_id": user_id
        }
    )

@sync_to_async
def create_thread(activity, user_id):
    return Thread.objects.create(activity=activity, user_id=user_id)

@sync_to_async
def get_thread_by_id(thread_id):
    return Thread.objects.get(id=thread_id)

@sync_to_async
def get_messages_for_thread(thread_id):
    return list(Message.objects.filter(thread_id=thread_id).order_by('message_number'))

@sync_to_async
def get_or_create_thread(activity, user_id):
    thread, created = Thread.objects.get_or_create(
        activity=activity,
        user_id=user_id,
    )
    if not created:
        thread.save(update_fields=['updated_at'])
        logger.info(f"Existing thread found and updated: {thread.id}")
    else:
        logger.info(f"New thread created: {thread.id}")
    return thread

@cl.on_chat_start
async def on_chat_start():
    referer_url = cl.user_session.get("http_referer", "")
    
    parsed_url = urllib.parse.urlparse(referer_url)
    query_string = parsed_url.query
    query_params = dict(urllib.parse.parse_qsl(query_string))
    
    logger.info(f"Referer URL: {referer_url}")
    logger.info(f"Query string: {query_string}")
    logger.info(f"Parsed parameters: {query_params}")
    
    activity_id = query_params.get('activity_id')
    user_id = query_params.get('user_id')
    username = query_params.get('username', 'User')
    
    logger.info(f"activity_id: {activity_id}")
    logger.info(f"user_id: {user_id}")
    
    if not activity_id or not user_id:
        await cl.Message(content=f"Invalid parameters. Activity ID and User ID are required. Received params: {query_params}").send()
        raise Exception("Invalid parameters")
    
    try:
        activity = await get_activity_by_id(activity_id)
        thread = await get_or_create_thread(activity, user_id) 
        cl.user_session.set("thread_id", thread.id)
        cl.user_session.set("activity_id", activity_id)
        cl.user_session.set("user_id", user_id)
        cl.user_session.set("username", username)
        
        course_title = await get_course_title(activity)

        questions = getattr(activity, 'questions', [])
        main_question = None
        if questions and isinstance(questions, list) and len(questions) > 0:
            main_question = questions[0]
        else:
            main_question = getattr(activity, 'title', None)

        welcome_message = f"Welcome to SIMBA! You are in the activity: **{activity.title}**, course: **{course_title}**"
        await cl.Message(content=welcome_message).send()

        if main_question:
            question_message = f"Main question for this activity: **{main_question}**"
            await cl.Message(content=question_message).send()
        
        previous_messages = await get_messages_for_thread(thread.id)
        for msg in previous_messages:
            author = msg.metadata.get('author') if msg.metadata else None
            if msg.role == 'assistant':
                await cl.Message(content=msg.content, author='Assistant').send()
            else:
                await cl.Message(content=msg.content, author=author, type="user_message").send()
        
    except Activity.DoesNotExist:
        await cl.Message(content="Activity not found. Please check the provided ID.").send()
        raise Exception("Activity not found")

@cl.on_message
async def on_message(message: cl.Message):
    activity_id = cl.user_session.get("activity_id")
    user_id = cl.user_session.get("user_id")
    username = cl.user_session.get("username")

    if not activity_id or not user_id:
        await cl.Message(content="Invalid session. Please refresh the page.").send()
        return

    try:
        thread_id = cl.user_session.get("thread_id")
        thread = await get_thread_by_id(thread_id)
        activity = await get_activity_by_id(activity_id) 
        await create_user_message(thread, message.content, user_id, username)
        messages = await get_messages_for_thread(thread_id)
        openai_messages = []

        attitude = getattr(activity, 'agent_attitude', 'friendly')
        subjects = getattr(activity, 'subjects', '')
        restrict = getattr(activity, 'restrict_to_subject', False)
        allow_questions = getattr(activity, 'allow_questions', True)
        allow_emojis = getattr(activity, 'allow_emojis', True)
        trust_document = getattr(activity, 'trust_document', True)
        expert_mode = getattr(activity, 'expert_mode', False)
        custom_prompt = getattr(activity, 'custom_prompt', '')
        description = getattr(activity, 'description', '')
        questions = getattr(activity, 'questions', [])

        main_question = None
        if questions and isinstance(questions, list) and len(questions) > 0:
            main_question = questions[0]
        else:
            main_question = getattr(activity, 'title', None)

        system_prompt = "You are an intelligent study assistant for students and teachers."
        system_prompt += f" Your attitude should be {attitude}."
        if description:
            system_prompt += f" Activity description: {description}."
        if main_question:
            system_prompt += f" The main question for this activity is: {main_question}."
        if subjects:
            system_prompt += f" Subjects: {subjects}."
        if restrict:
            system_prompt += " Only answer questions related to the course subjects."
        if not allow_questions:
            system_prompt += " Do not provide questions to the student unless explicitly asked."
        if not allow_emojis:
            system_prompt += " Do not use emojis in your responses."
        else:
            system_prompt += " You can use emojis to make the conversation more engaging."
        if trust_document:
            system_prompt += " Trust the provided document to help answer questions."
        if expert_mode and custom_prompt:
            system_prompt += f" {custom_prompt}"
        if questions:
            system_prompt += f" Example questions for this activity: {', '.join(questions)}."

        openai_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            if msg.role in ["assistant", "user"]:
                openai_role = msg.role
            else:
                openai_role = "user"
            openai_messages.append({"role": openai_role, "content": msg.content})
        response = await client.chat.completions.create(
            model=settings["model"],
            messages=openai_messages,
            temperature=settings["temperature"],
        )
        ai_response = response.choices[0].message.content
        await create_assistant_message(thread, ai_response, settings["model"], user_id)
        await cl.Message(content=ai_response).send()
    except Activity.DoesNotExist:
        await cl.Message(content="Activity not found. Please check the provided ID.").send()
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        await cl.Message(content=f"An error occurred while processing your message. Details: {str(e)}").send()

