import os
import django
from openai import AsyncOpenAI
import chainlit as cl
import json
import logging
import urllib.parse
from asgiref.sync import sync_to_async

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'simba.settings')
django.setup()

from simbaapp.models import Activity, Message, Topic, Course, User

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
def get_topic_by_id(topic_id):
    return Topic.objects.get(id=topic_id)

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
def get_messages_for_activity(activity_id):
    return list(Message.objects.filter(activity_id=activity_id).order_by('timestamp'))

@sync_to_async
def create_user_message(activity, content, user_id, username):
    return Message.objects.create(
        activity=activity,
        content=content,
        role="user",
        metadata={
            "user_id": user_id,
            "author": username
        }
    )
@sync_to_async
def create_assistant_message(activity, content, model, user_id):
    return Message.objects.create(
        activity=activity,
        content=content,
        role="assistant",
        metadata={
            "model": model,
            "user_id": user_id
        }
    )

@sync_to_async
def get_topic_from_course(course):
    return course.topic

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
    username = query_params.get('username', 'Usuário')
    lang = query_params.get('lang', 'fr')
    
    logger.info(f"activity_id: {activity_id}")
    logger.info(f"user_id: {user_id}")
    
    if not activity_id or not user_id:
        await cl.Message(content=f"Parâmetros inválidos. Activity ID e User ID são necessários. Params recebidos: {query_params}").send()
        raise Exception("Parâmetros inválidos")
    
    try:
        activity = await get_activity_by_id(activity_id)
        
        cl.user_session.set("activity_id", activity_id)
        cl.user_session.set("user_id", user_id)
        cl.user_session.set("username", username)
        cl.user_session.set("lang", lang)
        
        previous_messages = await get_messages_for_activity(activity_id)
        
        for msg in previous_messages:
            if msg.role == "user":
                await cl.Message(
                    content=msg.content,
                    author=msg.metadata.get('author', username) if msg.metadata else username
                ).send()
            else:
                await cl.Message(content=msg.content).send()
        
        course_title = await get_course_title(activity)

        questions = getattr(activity, 'questions', [])
        main_question = None
        if questions and isinstance(questions, list) and len(questions) > 0:
            main_question = questions[0]
        else:
            main_question = getattr(activity, 'title', None)

        welcome_msgs = {
            'en': f"Welcome to SIMBA! You are in the activity: **{activity.title}**, course: **{course_title}**",
            'fr': f"Bienvenue sur SIMBA ! Vous êtes dans l'activité : **{activity.title}**, du cours : **{course_title}**",
            'es': f"¡Bienvenido a SIMBA! Estás en la actividad: **{activity.title}**, del curso: **{course_title}**"
        }
        await cl.Message(content=welcome_msgs.get(lang, welcome_msgs['en'])).send()

        if main_question:
            question_msgs = {
                'en': f"Main question for this activity: **{main_question}**",
                'fr': f"Question principale de cette activité : **{main_question}**",
                'es': f"Pregunta principal de esta actividad: **{main_question}**"
            }
            await cl.Message(content=question_msgs.get(lang, question_msgs['en'])).send()
        
    except Activity.DoesNotExist:
        await cl.Message(content="Atividade não encontrada. Verifique o ID fornecido.").send()
        raise Exception("Atividade não encontrada")

@cl.on_message
async def on_message(message: cl.Message):
    activity_id = cl.user_session.get("activity_id")
    user_id = cl.user_session.get("user_id")
    username = cl.user_session.get("username")

    if not activity_id or not user_id:
        await cl.Message(content="Sessão inválida. Atualize a página.").send()
        return

    try:
        activity = await get_activity_by_id(activity_id)
        await create_user_message(activity, message.content, user_id, username)
        messages = await get_messages_for_activity(activity_id)
        openai_messages = []

        lang = cl.user_session.get("lang", "fr")
        attitude_map = {
            'friendly': {'en': 'friendly', 'fr': 'amical', 'es': 'amistoso'},
            'informal': {'en': 'informal', 'fr': 'informel', 'es': 'informal'},
            'formal': {'en': 'formal', 'fr': 'formel', 'es': 'formal'}
        }
        attitude = getattr(activity, 'agent_attitude', 'friendly')
        attitude_str = attitude_map.get(attitude, attitude_map['friendly'])[lang]
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

        base_prompts = {
            'en': "You are an intelligent study assistant for students and teachers.",
            'fr': "Vous êtes un assistant d'étude intelligent pour les étudiants et les enseignants.",
            'es': "Eres un asistente de estudio inteligente para estudiantes y profesores."
        }
        system_prompt = base_prompts.get(lang, base_prompts['en'])
        system_prompt += f" Your attitude should be {attitude_str}."
        if description:
            system_prompt += f" Activity description: {description}."
        if main_question:
            if lang == 'fr':
                system_prompt += f" La question principale de cette activité est : {main_question}."
            elif lang == 'es':
                system_prompt += f" La pregunta principal de esta actividad es: {main_question}."
            else:
                system_prompt += f" The main question for this activity is: {main_question}."
        if subjects:
            system_prompt += f" Subjects: {subjects}."
        if restrict:
            if lang == 'fr':
                system_prompt += " Ne répondez qu'aux questions liées aux sujets du cours."
            elif lang == 'es':
                system_prompt += " Solo responde preguntas relacionadas con los temas del curso."
            else:
                system_prompt += " Only answer questions related to the course subjects."
        if not allow_questions:
            if lang == 'fr':
                system_prompt += " Ne proposez pas de questions à l'étudiant sauf si cela est explicitement demandé."
            elif lang == 'es':
                system_prompt += " No propongas preguntas al estudiante a menos que se solicite explícitamente."
            else:
                system_prompt += " Do not provide questions to the student unless explicitly asked."
        if not allow_emojis:
            if lang == 'fr':
                system_prompt += " N'utilisez pas d'emojis dans vos réponses."
            elif lang == 'es':
                system_prompt += " No uses emojis en tus respuestas."
            else:
                system_prompt += " Do not use emojis in your responses."
        else:
            if lang == 'fr':
                system_prompt += " Vous pouvez utiliser des emojis pour rendre la conversation plus engageante."
            elif lang == 'es':
                system_prompt += " Puedes usar emojis para hacer la conversación más atractiva."
            else:
                system_prompt += " You can use emojis to make the conversation more engaging."
        if trust_document:
            if lang == 'fr':
                system_prompt += " Faites confiance au document fourni pour aider à répondre aux questions."
            elif lang == 'es':
                system_prompt += " Confía en el documento proporcionado para ayudar a responder preguntas."
            else:
                system_prompt += " Trust the provided document to help answer questions."
        if expert_mode and custom_prompt:
            system_prompt += f" {custom_prompt}"
        if questions:
            if lang == 'fr':
                system_prompt += f" Exemples de questions pour cette activité : {', '.join(questions)}."
            elif lang == 'es':
                system_prompt += f" Ejemplos de preguntas para esta actividad: {', '.join(questions)}."
            else:
                system_prompt += f" Example questions for this activity: {', '.join(questions)}."

        openai_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            openai_messages.append({"role": msg.role, "content": msg.content})
        response = await client.chat.completions.create(
            model=settings["model"],
            messages=openai_messages,
            temperature=settings["temperature"],
        )
        ai_response = response.choices[0].message.content
        await create_assistant_message(activity, ai_response, settings["model"], user_id)
        await cl.Message(content=ai_response).send()
    except Activity.DoesNotExist:
        await cl.Message(content="Atividade não encontrada. Verifique o ID fornecido.").send()
    except Exception as e:
        logger.error(f"Erro ao processar mensagem: {str(e)}")
        await cl.Message(content=f"Ocorreu um erro ao processar sua mensagem. Detalhes: {str(e)}").send()

