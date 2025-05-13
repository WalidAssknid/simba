import os
import django
import django.apps
from openai import AsyncOpenAI
import chainlit as cl
import logging
import urllib.parse
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SIMBA_API_BASE_URL = os.getenv('SIMBA_API_URL', 'http://web:8000/api')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'simba.settings')
if not django.apps.apps.ready:
    django.setup()
from simbaapp.models import Activity, Message, Thread, User # Will not be used anymore

client = AsyncOpenAI()

settings = {
    "model": "gpt-4o-mini",
    "temperature": 0.7,
}

# --- API Client Helpers ---
async def api_get_activity(activity_id: int):
    async with httpx.AsyncClient() as http_client:
        try:
            response = await http_client.get(f"{SIMBA_API_BASE_URL}/activities/{activity_id}")
            response.raise_for_status() 
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"API Error getting activity {activity_id}: {e.response.status_code} - {e.response.text}")
            raise Exception(f"API Error: Could not fetch activity. Status: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Request Error getting activity {activity_id}: {e}")
            raise Exception(f"Request Error: Could not connect to API to fetch activity.")

async def api_get_or_create_thread(activity_id: int, user_id: int):
    payload = {"activity_id": activity_id, "user_id": user_id}
    async with httpx.AsyncClient() as http_client:
        try:
            response = await http_client.post(f"{SIMBA_API_BASE_URL}/threads/get-or-create", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"API Error get/create thread: {e.response.status_code} - {e.response.text}")
            raise Exception(f"API Error: Could not get/create thread. Status: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Request Error get/create thread: {e}")
            raise Exception(f"Request Error: Could not connect to API for thread.")

async def api_create_message(thread_id: int, content: str, role: str, user_id: int, username: str = None, model_name: str = None):
    payload = {
        "thread_id": thread_id, 
        "content": content,
        "role": role,
        "user_id": user_id,
        "username": username,
        "model": model_name
    }
    async with httpx.AsyncClient() as http_client:
        try:
            response = await http_client.post(f"{SIMBA_API_BASE_URL}/threads/{thread_id}/messages", json=payload)
            response.raise_for_status()
            return response.json() 
        except httpx.HTTPStatusError as e:
            logger.error(f"API Error creating message: {e.response.status_code} - {e.response.text}")
            raise Exception(f"API Error: Could not create message. Status: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Request Error creating message: {e}")
            raise Exception(f"Request Error: Could not connect to API for message.")

async def api_get_messages_for_thread(thread_id: int):
    async with httpx.AsyncClient() as http_client:
        try:
            response = await http_client.get(f"{SIMBA_API_BASE_URL}/threads/{thread_id}/messages")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"API Error getting messages: {e.response.status_code} - {e.response.text}")
            raise Exception(f"API Error: Could not fetch messages. Status: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Request Error getting messages: {e}")
            raise Exception(f"Request Error: Could not connect to API for messages.")

@cl.on_chat_start
async def on_chat_start():
    referer_url = cl.user_session.get("http_referer", "")
    parsed_url = urllib.parse.urlparse(referer_url)
    query_params = dict(urllib.parse.parse_qsl(parsed_url.query))
    
    activity_id_str = query_params.get('activity_id')
    user_id_str = query_params.get('user_id')
    username = query_params.get('username', 'User')
    
    if not activity_id_str or not user_id_str:
        await cl.Message(content=f"Invalid parameters. Activity ID and User ID are required. Received: {query_params}").send()
        raise Exception("Invalid parameters: activity_id and user_id are required.")

    try:
        activity_id = int(activity_id_str)
        user_id = int(user_id_str)
    except ValueError:
        await cl.Message(content="Invalid Activity ID or User ID format.").send()
        raise Exception("Invalid ID format")

    try:
        activity_data = await api_get_activity(activity_id)
        activity_title = activity_data.get('title', 'Activity')

        thread_data = await api_get_or_create_thread(activity_id, user_id)
        thread_id = thread_data['id']
        
        cl.user_session.set("thread_id", thread_id)
        cl.user_session.set("activity_id", activity_id)
        cl.user_session.set("user_id", user_id)
        cl.user_session.set("username", username)
        cl.user_session.set("activity_data", activity_data)

        welcome_message = f"Welcome to SIMBA! You are in the activity: **{activity_title}**."
        await cl.Message(content=welcome_message).send()

        questions = activity_data.get('questions', [])
        main_question = questions[0] if questions and isinstance(questions, list) and questions else activity_data.get('title')

        if main_question:
            question_message = f"Main question for this activity: **{main_question}**"
            await cl.Message(content=question_message).send()
        
        previous_messages_data = await api_get_messages_for_thread(thread_id)
        for msg_data in previous_messages_data:
            author = msg_data.get('metadata', {}).get('author') if msg_data.get('metadata') else msg_data.get('role')
            if msg_data['role'] == 'assistant':
                await cl.Message(content=msg_data['content'], author='Assistant').send()
            else:
                await cl.Message(content=msg_data['content'], author=author, type="user_message").send()
        
    except Exception as e:
        logger.error(f"Error during chat start: {e}")
        await cl.Message(content=f"Could not start chat: {str(e)}").send()
        raise

@cl.on_message
async def on_message(message: cl.Message):
    activity_id = cl.user_session.get("activity_id")
    user_id = cl.user_session.get("user_id")
    username = cl.user_session.get("username")
    thread_id = cl.user_session.get("thread_id")
    activity_data = cl.user_session.get("activity_data")

    if not all([activity_id, user_id, thread_id, activity_data]):
        await cl.Message(content="Session error. Please refresh and try again.").send()
        return

    try:
        await api_create_message(thread_id, message.content, "user", user_id, username=username)
        
        messages_history_data = await api_get_messages_for_thread(thread_id)
        openai_messages = []

        attitude = activity_data.get('agent_attitude', 'friendly')
        subjects = activity_data.get('subjects', '')
        restrict = activity_data.get('restrict_to_subject', False)
        allow_q = activity_data.get('allow_questions', True)
        allow_e = activity_data.get('allow_emojis', True)
        trust_doc = activity_data.get('trust_document', True)
        expert = activity_data.get('expert_mode', False)
        custom_p = activity_data.get('custom_prompt', '')
        description = activity_data.get('description', '')
        questions = activity_data.get('questions', [])
        main_question = questions[0] if questions and isinstance(questions, list) and questions else activity_data.get('title')

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
        if not allow_q:
            system_prompt += " Do not provide questions to the student unless explicitly asked."
        if not allow_e:
            system_prompt += " Do not use emojis in your responses."
        else:
            system_prompt += " You can use emojis to make the conversation more engaging."
        if trust_doc:
            system_prompt += " Trust the provided document to help answer questions."
        if expert and custom_p:
            system_prompt += f" {custom_p}"
        if questions:
            system_prompt += f" Example questions for this activity: {', '.join(questions)}."

        openai_messages.append({"role": "system", "content": system_prompt})
        for msg_data in messages_history_data:
            openai_role = msg_data['role'] if msg_data['role'] in ["assistant", "user"] else "user"
            openai_messages.append({"role": openai_role, "content": msg_data['content']})
            
        response = await client.chat.completions.create(
            model=settings["model"],
            messages=openai_messages,
            temperature=settings["temperature"],
        )
        ai_response_content = response.choices[0].message.content
        
        await api_create_message(thread_id, ai_response_content, "assistant", user_id, model_name=settings["model"])
        await cl.Message(content=ai_response_content).send()
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await cl.Message(content=f"An error occurred: {str(e)}").send()

