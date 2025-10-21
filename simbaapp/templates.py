import logging
import gettext
import os

locale_dir = os.path.join(os.path.dirname(__file__), "..", "locale")

def get_gettext_function(lang):
    translations = gettext.translation('django', localedir=locale_dir, languages=[lang], fallback=True)
    return translations.gettext


def get_language_prompts(language_code: str = 'en') -> dict:
    """Get prompts in different languages"""
    prompts = {
        'en': {
            'intro': "You are a {adj1} {teaching_adj_str} tutor for the course '{courseName}'.",
            'name_intro': "Your name is SIMBA 😸 (Sistema Inteligente de Medición, Bienestar y Apoyo) and you were created by the Núcleo Milenio de Educación Superior and IRIT Talent team.",
            'greeting': "Hello! 😸 I am SIMBA, and I will help you reflect on the following questions: ",
            'help_text': "Help the student answer the following questions:",
            'respond_style': "Respond in a {adj1}, concise and proactive way",
        },
        'fr': {
            'intro': "Vous êtes un tuteur {adj1} {teaching_adj_str} pour le cours '{courseName}'.",
            'name_intro': "Votre nom est SIMBA 😸 (Sistema Inteligente de Medición, Bienestar y Apoyo) et vous avez été créé par le Núcleo Milenio de Educación Superior et l'équipe IRIT Talent.",
            'greeting': "Bonjour ! 😸 Je suis SIMBA, et je vais vous aider à réfléchir sur les questions suivantes : ",
            'help_text': "Aidez l'étudiant à répondre aux questions suivantes :",
            'respond_style': "Répondez de manière {adj1}, concise et proactive",
        },
        'es': {
            'intro': "Eres un tutor {adj1} {teaching_adj_str} para el curso '{courseName}'.",
            'name_intro': "Tu nombre es SIMBA 😸 (Sistema Inteligente de Medición, Bienestar y Apoyo) y fuiste creado por el Núcleo Milenio de Educación Superior y el equipo IRIT Talent.",
            'greeting': "¡Hola! 😸 Soy SIMBA, y te ayudaré a reflexionar sobre las siguientes preguntas: ",
            'help_text': "Ayuda al estudiante a responder las siguientes preguntas:",
            'respond_style': "Responde de manera {adj1}, concisa y proactiva",
        },
        'pt': {
            'intro': "Você é um tutor {adj1} {teaching_adj_str} para o curso '{courseName}'.",
            'name_intro': "Seu nome é SIMBA 😸 (Sistema Inteligente de Medición, Bienestar y Apoyo) e você foi criado pelo Núcleo Milenio de Educación Superior e equipe IRIT Talent.",
            'greeting': "Olá! 😸 Eu sou SIMBA, e vou te ajudar a refletir sobre as seguintes questões: ",
            'help_text': "Ajude o estudante a responder as seguintes questões:",
            'respond_style': "Responda de forma {adj1}, concisa e proativa",
        }
    }
    
    return prompts.get(language_code, prompts['en'])

def get_first_message(activity_data: dict, logger_instance: logging.Logger, language_code: str = 'en') -> str:
    first_message = ""
    return first_message

def build_system_prompt(activity_data: dict, logger_instance: logging.Logger, language_code: str = 'en') -> str:
    _ = get_gettext_function(language_code)

    adj1 = activity_data.get('agent_attitude', 'friendly')
    expert_mode = activity_data.get('expert_mode', False)
    
    activity_title = activity_data.get('title', '')
    activity_description = activity_data.get('description', '')
    
    course_info = activity_data.get('course', {})
    if isinstance(course_info, dict):
        courseName = course_info.get('title', 'this course')
    else: 
        courseName = _('this course')
        logger_instance.warning(f"Course information might be missing or not in expected format in activity_data for activity {activity_data.get('id')}")

    allow_emojis_flag = activity_data.get('allow_emojis', True)
    questions_list = activity_data.get('questions', [])
    activity_subjects = activity_data.get('subjects', '')
    restrict_to_subject_flag = activity_data.get('restrict_to_subject', False)
    trust_document_flag = activity_data.get('trust_document', True)
    word_limit_val = activity_data.get('word_limit', 0)
    custom_prompt_text = activity_data.get('custom_prompt', '')
    allow_bot_to_ask_questions_flag = activity_data.get('allow_questions', True)
    vector_store_id = activity_data.get('vector_store_id')

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

    def answersGen_str(is_expert_mode, never_answer_directly):
        if never_answer_directly:
            return "You should never give direct answers to the questions. Instead, guide the student to discover the answer through questioning and hints."
        elif is_expert_mode:
            return "You should not give the answer, but guide the student to answer."
        else:
            return "You can provide an answer to the provided questions if the student asks for it."

    def teachTypeGen_str(is_expert_mode):
        return "Act as a Socratic tutor, taking the initiative in getting the students to answer the questions."

    def teachingAdjGen_str(is_expert_mode):
        return "socratic" if is_expert_mode else "standard"

    def docsGen_str(mentiondocuments, has_files):
        nstr = ""
        if mentiondocuments and has_files:
            nstr = "You have access to uploaded documents for this activity. Use these documents to help answer questions and encourage students to reference them when appropriate."
        elif mentiondocuments and not has_files:
            nstr = "Encourage them to go and read a section of the provided documents to answer."
        elif has_files:
            nstr = "You have access to uploaded documents for this activity that you can reference to help students."
        return nstr

    def filesGen_str(has_files):
        if has_files:
            return "\n\nIMPORTANT: This activity has uploaded files/documents available. You can search through and reference these documents to provide more accurate and detailed responses. When relevant, cite information from these documents and encourage students to explore them."
        return ""

    def limitsGen_str(limit):
        if limit and limit != 0:
            return f"Your answers should be {limit} words maximum."
        return ""

    def activityContextGen_str(title, description):
        """Generate activity-specific context for the prompt"""
        context_str = ""
        if title and description:
            context_str = f"This specific activity is titled '{title}' and focuses on: {description}.\n\n"
        elif title:
            context_str = f"This specific activity is titled '{title}'.\n\n"
        elif description:
            context_str = f"This activity focuses on: {description}.\n\n"
        return context_str

    has_files = bool(vector_store_id)

    emojis_str = emojiGen(allow_emojis_flag)
    questions_str = questionsGen_str(questions_list)
    subjects_str = subjectsGen_str(activity_subjects, restrict_to_subject_flag)
    teaching_adj_str = teachingAdjGen_str(expert_mode)
    never_answer_directly_flag = activity_data.get('never_answer_directly', True)
    answers_text = answersGen_str(expert_mode, never_answer_directly_flag)
    teaching_type_text = teachTypeGen_str(expert_mode)
    documents_str = docsGen_str(trust_document_flag, has_files)
    files_str = filesGen_str(has_files)
    limits_str = limitsGen_str(word_limit_val)
    activity_context_str = activityContextGen_str(activity_title, activity_description)

    # Get language-specific prompts
    lang_prompts = get_language_prompts(language_code)
    
    full_template = f"""{lang_prompts['intro'].format(adj1=adj1, teaching_adj_str=teaching_adj_str, courseName=courseName)}

{activity_context_str}{lang_prompts['name_intro']}
{lang_prompts['respond_style'].format(adj1=adj1)}{emojis_str}

{lang_prompts['help_text']}

{questions_str}

{subjects_str}

{answers_text} {teaching_type_text}

{documents_str}

Your first message should begin with '{lang_prompts['greeting']}' Followed by the questions to answer.

{limits_str}{files_str}"""
    system_prompt = full_template.strip()
    if expert_mode and custom_prompt_text:
        system_prompt += f"\n\n{custom_prompt_text}"
    if not allow_bot_to_ask_questions_flag:
        system_prompt += "\n\nDo not provide questions to the student unless explicitly asked."
    return system_prompt