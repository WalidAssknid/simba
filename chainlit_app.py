import os
import django
import django.apps
from openai import AsyncOpenAI
import chainlit as cl
import logging
import httpx
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global session storage
SIMBA_SESSION_STORAGE = {}

def get_session_data_from_api(session_id: str):
    """Get session data from API using session ID"""
    if session_id in SIMBA_SESSION_STORAGE:
        return SIMBA_SESSION_STORAGE[session_id]
    
    return None

async def fetch_session_data_from_api(session_id: str):
    """Fetch session data from API asynchronously"""
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(f"{SIMBA_API_BASE_URL}/chainlit/session/{session_id}")
            if response.status_code == 200:
                session_data = response.json()
                SIMBA_SESSION_STORAGE[session_id] = session_data
                return session_data
            else:
                logger.warning(f"Session {session_id} not found in API: {response.status_code}")
                return None
    except Exception as e:
        logger.error(f"Error fetching session data from API: {e}")
        return None

def get_simba_params():
    """Extract parameters from session data or fallback to URL"""
    params = {}
    
    logger.info("Starting parameter extraction...")
    
    current_url = None
    
    if hasattr(cl, 'context') and hasattr(cl.context, 'session'):
        if hasattr(cl.context.session, 'root_url'):
            current_url = cl.context.session.root_url
            logger.info(f"Got URL from context.session.root_url: {current_url}")
        elif hasattr(cl.context.session, 'http_referer'):
            current_url = cl.context.session.http_referer
            logger.info(f"Got URL from context.session.http_referer: {current_url}")
    
    if not current_url and hasattr(cl, 'user_session'):
        current_url = cl.user_session.get("http_referer", "")
        logger.info(f"Got URL from user_session: {current_url}")
    
    if not current_url:
        try:
            import chainlit.context as ctx
            if hasattr(ctx, 'context') and ctx.context and hasattr(ctx.context, 'session'):
                if hasattr(ctx.context.session, 'headers'):
                    referer = ctx.context.session.headers.get('referer')
                    if referer:
                        current_url = referer
                        logger.info(f"Got URL from headers referer: {current_url}")
        except Exception as e:
            logger.warning(f"Could not get URL from headers: {e}")
    
    if current_url:
        from urllib.parse import urlparse, parse_qs
        parsed_url = urlparse(current_url)
        url_params = parse_qs(parsed_url.query)
        logger.info(f"Parsed URL params: {url_params}")
        
        session_id = url_params.get('session_id', [None])[0]
        if session_id:
            logger.info(f"Found session_id in URL: {session_id}")
            session_data = get_session_data_from_api(session_id)
            if session_data:
                logger.info(f"Retrieved session data for session_id: {session_id}")
                return {
                    'activity_id': str(session_data['activity_id']),
                    'user_id': str(session_data['user_id']),
                    'username': session_data['username'],
                    'thread_id': str(session_data['thread_id']),
                    'session_id': session_id,
                    'activity_data': session_data['activity_data']
                }
            else:
                logger.warning(f"No session data found for session_id: {session_id}")
        
        for key, values in url_params.items():
            if values:
                params[key] = values[0]
                logger.info(f"Found URL param: {key} = {values[0]}")
    else:
        logger.warning("No URL found in any context")
    
    if hasattr(cl, 'user_session'):
        for key in ['activity_id', 'user_id', 'username', 'thread_id', 'session_id']:
            value = cl.user_session.get(key)
            if value:
                params[key] = value
                logger.info(f"Found user_session param: {key} = {value}")
    
    logger.info(f"Final extracted params: {params}")
    return params

SIMBA_API_BASE_URL = os.getenv('SIMBA_API_URL', 'http://web:8000/api')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'simba.settings')
if not django.apps.apps.ready:
    django.setup()

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

async def api_init_session(activity_id: int, user_id: int, username: str, thread_id: int = None):
    """Initialize session via API"""
    payload = {
        "activity_id": activity_id,
        "user_id": user_id,
        "username": username
    }
    if thread_id:
        payload["thread_id"] = thread_id
        
    async with httpx.AsyncClient() as http_client:
        try:
            response = await http_client.post(f"{SIMBA_API_BASE_URL}/chainlit/init-session", json=payload)
            response.raise_for_status()
            session_data = response.json()
            
            SIMBA_SESSION_STORAGE[session_data['session_id']] = session_data
            
            return session_data
        except httpx.HTTPStatusError as e:
            logger.error(f"API Error initializing session: {e.response.status_code} - {e.response.text}")
            raise Exception(f"API Error: Could not initialize session. Status: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Request Error initializing session: {e}")
            raise Exception(f"Request Error: Could not connect to API for session initialization.")

async def _build_system_prompt(activity_data: dict, logger_instance: logging.Logger) -> str:
    adj1 = activity_data.get('agent_attitude', 'friendly')
    expert_mode = activity_data.get('expert_mode', False)
    
    course_info = activity_data.get('course', {})
    if isinstance(course_info, dict):
        courseName = course_info.get('title', 'this course')
    else: 
        courseName = 'this course'
        logger_instance.warning(f"Course information might be missing or not in expected format in activity_data for activity {activity_data.get('id')}")

    allow_emojis_flag = activity_data.get('allow_emojis', True)
    questions_list = activity_data.get('questions', [])
    activity_subjects = activity_data.get('subjects', '')
    restrict_to_subject_flag = activity_data.get('restrict_to_subject', False)
    trust_document_flag = activity_data.get('trust_document', True)
    word_limit_val = activity_data.get('word_limit', 0)
    custom_prompt_text = activity_data.get('custom_prompt', '')
    allow_bot_to_ask_questions_flag = activity_data.get('allow_questions', True)

    def emojiGen(useEmojis):
        return ", using emojis where possible." if useEmojis else "."

    def questionsGen_str(questions):
        nstr = ""
        if questions and isinstance(questions, list):
            for i, q_item in enumerate(questions):
                question_text = q_item if isinstance(q_item, str) else q_item.get('text', '') 
                if question_text:
                    nstr += f"Question {i+1} : {question_text} \n"
        return nstr.strip()

    def subjectsGen_str(subjects, restricted):
        nstr = ""
        if subjects:
            nstr += "You should help the student to reflect in depth on the following course subjects :\n <Beginning of the course subjects>\n"
            nstr += subjects
            nstr += "\n<end of the course subjects>\n"
        if restricted:
            nstr += "You should only speak of those listed subjects. Avoid as much as possible speaking of other subjects, and steer back the student to the course subjects if he tries to deviate from them."
        return nstr

    def answersGen_str(is_expert_mode):
        if is_expert_mode:
            return "You should not give the answer, but guide the student to answer."
        else:
            return "You can provide an answer to the provided questions if the student asks for it."

    def teachTypeGen_str(is_expert_mode):
        if is_expert_mode:
            return "Act as a Socratic tutor, taking the initiative in getting the students to answer the questions."
        else:
            return "Act as a standard teacher."

    def teachingAdjGen_str(is_expert_mode):
        return "socratic" if is_expert_mode else "standard"

    def docsGen_str(mentiondocuments):
        nstr = ""
        if mentiondocuments:
            nstr = "Encourage them to go and read a section of the provided documents to answer."
        return nstr

    def limitsGen_str(limit):
        if limit and limit != 0:
            return f"Your answers should be {limit} words maximum."
        return ""

    emojis_str = emojiGen(allow_emojis_flag)
    questions_str = questionsGen_str(questions_list)
    subjects_str = subjectsGen_str(activity_subjects, restrict_to_subject_flag)
    teaching_adj_str = teachingAdjGen_str(expert_mode)
    answers_text = answersGen_str(expert_mode)
    teaching_type_text = teachTypeGen_str(expert_mode)
    documents_str = docsGen_str(trust_document_flag)
    limits_str = limitsGen_str(word_limit_val)

    full_template = f"""You are a {adj1} {teaching_adj_str} tutor for the course '{courseName}'.

Your name is SIMBA 😸 (Sistema Inteligente de Medición, Bienestar y Apoyo) and you were created by the Núcleo Milenio de Educación Superior and IRIT Talent team.
Respond in a {adj1}, concise and proactive way{emojis_str}

Help the student answer the following questions:

{questions_str}

{subjects_str}

{answers_text} {teaching_type_text}

{documents_str}

Your first message should begin with 'Hello! 😸 I am SIMBA, and I will help you reflect on the following questions: ' Followed by the questions to answer.

{limits_str}"""
    system_prompt = full_template.strip()
    if expert_mode and custom_prompt_text:
        system_prompt += f"\n\n{custom_prompt_text}"
    if not allow_bot_to_ask_questions_flag:
        system_prompt += "\n\nDo not provide questions to the student unless explicitly asked."
    return system_prompt

@cl.on_chat_start
async def on_chat_start():
    print("Chainlit starting new chat session", flush=True)
    
    params = get_simba_params()
    logger.info(f"Received parameters: {params}")
    
    session_id = params.get('session_id')
    if session_id:
        logger.info(f"Found session_id: {session_id}, attempting to fetch session data")
        
        session_data = await fetch_session_data_from_api(session_id)
        
        if session_data:
            activity_id = session_data['activity_id']
            user_id = session_data['user_id']
            username = session_data['username']
            thread_id = session_data['thread_id']
            activity_data = session_data['activity_data']
            
            logger.info(f"Using session data: activity_id={activity_id}, user_id={user_id}, thread_id={thread_id}")
            
            cl.user_session.set("session_id", session_id)
            cl.user_session.set("activity_id", activity_id)
            cl.user_session.set("user_id", user_id)
            cl.user_session.set("username", username)
            cl.user_session.set("thread_id", thread_id)
            cl.user_session.set("activity_data", activity_data)
            
        else:
            logger.error(f"Could not fetch session data for session_id: {session_id}")
            await cl.Message(content=f"Session expired or not found. Please refresh the page.").send()
            return
    else:
        activity_id_str = params.get('activity_id')
        user_id_str = params.get('user_id')
        username = params.get('username', 'User')
        thread_id_str = params.get('thread_id')
        
        logger.info(f"Fallback parameters - Activity: {activity_id_str}, User: {user_id_str}, Thread: {thread_id_str}")
        
        if not activity_id_str or not user_id_str:
            await cl.Message(content=f"Invalid parameters. Activity ID and User ID are required. Received: {params}").send()
            raise Exception("Invalid parameters: activity_id and user_id are required.")

        try:
            activity_id = int(activity_id_str)
            user_id = int(user_id_str)
            thread_id = int(thread_id_str) if thread_id_str else None
        except ValueError:
            await cl.Message(content="Invalid Activity ID, User ID, or Thread ID format.").send()
            raise Exception("Invalid ID format")

        try:
            session_data = await api_init_session(activity_id, user_id, username, thread_id)
            
            session_id = session_data['session_id']
            thread_id = session_data['thread_id']
            activity_data = session_data['activity_data']
            
            logger.info(f"Initialized new session: {session_id}")
            
            cl.user_session.set("session_id", session_id)
            cl.user_session.set("activity_id", activity_id)
            cl.user_session.set("user_id", user_id)
            cl.user_session.set("username", username)
            cl.user_session.set("thread_id", thread_id)
            cl.user_session.set("activity_data", activity_data)
            
        except Exception as e:
            logger.error(f"Failed to initialize session via API, falling back to direct method: {e}")
            
            activity_data = await api_get_activity(activity_id)
            
            if thread_id:
                thread_data = {'id': thread_id}
                logger.info(f"Using specific thread: {thread_id}")
            else:
                thread_data = await api_get_or_create_thread(activity_id, user_id)
                thread_id = thread_data['id']
                logger.info(f"Using default/created thread: {thread_id}")
            
            cl.user_session.set("thread_id", thread_id)
            cl.user_session.set("activity_id", activity_id)
            cl.user_session.set("user_id", user_id)
            cl.user_session.set("username", username)
            cl.user_session.set("activity_data", activity_data)

    try:    
        previous_messages_data = await api_get_messages_for_thread(thread_id)
        logger.info(f"Loaded {len(previous_messages_data) if previous_messages_data else 0} previous messages for thread {thread_id}")
        
        if previous_messages_data:
            for i, msg in enumerate(previous_messages_data[:3]):
                logger.info(f"Message {i+1} (Thread {thread_id}): Role={msg.get('role')}, Content={msg.get('content')[:50]}...")
        
        if not previous_messages_data: 
            system_prompt_content = await _build_system_prompt(activity_data, logger)
            
            openai_initial_messages = [{"role": "system", "content": system_prompt_content}]
            
            response = await client.chat.completions.create(
                model=settings["model"],
                messages=openai_initial_messages,
                temperature=settings["temperature"],
            )
            ai_first_response_content = response.choices[0].message.content
            
            await api_create_message(thread_id, ai_first_response_content, "assistant", user_id, model_name=settings["model"])
            await cl.Message(content=ai_first_response_content).send()
            logger.info(f"Created initial message for new thread {thread_id}")
            
        else: 
            if previous_messages_data: 
                logger.info(f"Sending {len(previous_messages_data)} messages to Chainlit interface for thread {thread_id}")
                for i, msg_data in enumerate(previous_messages_data):
                    author = msg_data.get('metadata', {}).get('author') if msg_data.get('metadata') else msg_data.get('role')
                    if msg_data['role'] == 'assistant':
                        await cl.Message(content=msg_data['content'], author='Assistant').send()
                        logger.info(f"Sent assistant message {i+1}: {msg_data['content'][:30]}...")
                    else:
                        await cl.Message(content=msg_data['content'], author=author, type="user_message").send() 
                        logger.info(f"Sent user message {i+1}: {msg_data['content'][:30]}...")
                logger.info(f"Finished sending all {len(previous_messages_data)} messages for thread {thread_id}")
        
    except Exception as e:
        logger.error(f"Error during chat start: {e}")
        await cl.Message(content=f"Could not start chat: {str(e)}").send()
        raise

@cl.on_message
async def on_message(message: cl.Message):
    activity_id = cl.user_session.get("activity_id")
    user_id = cl.user_session.get("user_id")
    username = cl.user_session.get("username", "User")
    thread_id = cl.user_session.get("thread_id")
    activity_data = cl.user_session.get("activity_data")
    session_id = cl.user_session.get("session_id")
    
    if not activity_id or not user_id or not thread_id:
        logger.info("Some parameters missing from session, checking SIMBA_SESSION_STORAGE")
        if not activity_id:
            activity_id = SIMBA_SESSION_STORAGE.get('activity_id')
        if not user_id:
            user_id = SIMBA_SESSION_STORAGE.get('user_id')
        if not thread_id:
            thread_id = SIMBA_SESSION_STORAGE.get('thread_id')
        if not username:
            username = SIMBA_SESSION_STORAGE.get('username', 'User')
    
    logger.info(f"Parameters for message - Activity: {activity_id}, User: {user_id}, Thread: {thread_id}, Session: {session_id}")

    if not all([activity_id, user_id, thread_id, activity_data]):
        logger.error(f"Missing required parameters - Activity: {activity_id}, User: {user_id}, Thread: {thread_id}")
        await cl.Message(content="Session error. Please refresh and try again.").send()
        return

    try:
        await api_create_message(thread_id, message.content, "user", user_id, username=username)
        
        openai_assistant_id = activity_data.get('openai_assistant_id')
        
        if openai_assistant_id:
            try:
                openai_thread_id = cl.user_session.get("openai_thread_id")
                if not openai_thread_id:
                    openai_thread = await client.beta.threads.create()
                    openai_thread_id = openai_thread.id
                    cl.user_session.set("openai_thread_id", openai_thread_id)
                    logger.info(f"Created new OpenAI thread: {openai_thread_id}")
                
                await client.beta.threads.messages.create(
                    thread_id=openai_thread_id,
                    role="user",
                    content=message.content
                )
                
                run = await client.beta.threads.runs.create(
                    thread_id=openai_thread_id,
                    assistant_id=openai_assistant_id
                )
                
                while run.status in ['queued', 'in_progress']:
                    await asyncio.sleep(1)
                    run = await client.beta.threads.runs.retrieve(
                        thread_id=openai_thread_id,
                        run_id=run.id
                    )
                
                if run.status == 'completed':
                    messages = await client.beta.threads.messages.list(
                        thread_id=openai_thread_id,
                        limit=1
                    )
                    
                    if messages.data:
                        latest_message = messages.data[0]
                        if latest_message.content:
                            ai_response_content = latest_message.content[0].text.value
                            
                            await api_create_message(thread_id, ai_response_content, "assistant", user_id, model_name="gpt-4o-mini")
                            
                            await cl.Message(content=ai_response_content).send()
                        else:
                            await cl.Message(content="I apologize, but I couldn't generate a response. Please try again.").send()
                    else:
                        await cl.Message(content="I apologize, but I couldn't retrieve the response. Please try again.").send()
                else:
                    logger.error(f"OpenAI run failed with status: {run.status}")
                    await cl.Message(content="I apologize, but I encountered an error processing your request. Please try again.").send()
                    
            except Exception as e:
                logger.error(f"OpenAI Assistant API Error: {e}")
                await cl.Message(content=f"I apologize, but I'm having trouble processing your request right now. Please try again in a moment. Error: {str(e)}").send()
                
        else:
            logger.info("Using legacy chat completions mode (no OpenAI assistant)")
            
            system_prompt_content = await _build_system_prompt(activity_data, logger)
            
            messages_history_data = await api_get_messages_for_thread(thread_id)
            openai_messages = [{"role": "system", "content": system_prompt_content}]

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

