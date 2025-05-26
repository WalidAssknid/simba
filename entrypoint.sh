#!/bin/sh
set -e

echo "Starting application initialization..."

python manage.py migrate

echo "Checking if default teacher exists..."
python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'simba.settings')
import django
django.setup()
from django.contrib.auth.hashers import make_password
from simbaapp.models import User, Course, Activity, CourseEnrollment

# Check if user already exists
if not User.objects.filter(username='prof').exists():
    # Create a new teacher user
    password = 'prof'
    password_hash = make_password(password)
    
    teacher = User.objects.create(
        username='prof',
        email='prof@gmail.com',
        password_hash=password_hash,
        role='teacher'
    )
    print('Default teacher user created successfully')
else:
    teacher = User.objects.get(username='prof')
    print('Default teacher user already exists')

# Create default course if it doesn't exist
if not Course.objects.filter(title='ct').exists():
    course = Course.objects.create(
        title='ct',
        description='cd',
        owner=teacher
    )
    print('Default course created successfully')
else:
    course = Course.objects.get(title='ct')
    print('Default course already exists')

# Create default activity if it doesn't exist
if not Activity.objects.filter(title='at').exists():
    activity = Activity.objects.create(
        title='at',
        description='ad',
        course=course,
        owner=teacher
    )
    print('Default activity created successfully')
else:
    activity = Activity.objects.get(title='at')
    print('Default activity already exists')

# Check if default student exists
if not User.objects.filter(username='student').exists():
    # Create a new student user
    password = 'student'
    password_hash = make_password(password)
    
    student = User.objects.create(
        username='student',
        email='student@gmail.com',
        password_hash=password_hash,
        role='student'
    )
    print('Default student user created successfully')
else:
    student = User.objects.get(username='student')
    print('Default student user already exists')

# Enroll student in the default course if not already enrolled
course = Course.objects.get(title='ct')
if not CourseEnrollment.objects.filter(user=student, course=course).exists():
    CourseEnrollment.objects.create(
        user=student,
        course=course
    )
    print('Default student enrolled in default course successfully')
else:
    print('Default student already enrolled in default course')

from datetime import datetime
from django.utils import timezone
from simbaapp.models import Message, Thread

teacher = User.objects.get(username='prof')

# We'll use the existing 'at' activity instead of creating a new one
activity = Activity.objects.get(title='at')

# Create a thread for the activity 
thread = None
threads_for_student = Thread.objects.filter(user=student, activity=activity)
if threads_for_student.exists():
    thread = threads_for_student.first()
    print('Thread for activity already exists')
else:
    thread = Thread.objects.create(
        activity=activity,
        user=student
    )
    print('Thread for activity created successfully')

    # Add thermodynamics conversation messages
    messages = [
        {
            'role': 'assistant',
            'content': 'Bonjour ! Je suis SIMBA, et je vais vous aider à réfléchir aux questions suivantes:\n\n1. D\'après vous, quelles sont les 2 à 5 idées principales à retenir du cours sur la thermodynamique?\n2. Quelles questions vous posez-vous encore sur ces notions?\n3. Comment pourriez-vous mettre en pratique ces concepts?\n\nN\'hésitez pas à partager vos réflexions, et nous pourrons explorer ces sujets ensemble!'
        },
        {
            'role': 'user',
            'content': 'Je n\'ai pas compris le concept de particule. Peux-tu me l\'expliquer ?'
        },
        {
            'role': 'assistant',
            'content': 'Bien entendu ! Le concept de particule en thermodynamique est assez fondamental. Une particule, dans ce contexte, peut être vue comme une représentation d\'un composant individuel de la matière (comme un atome ou une molécule) qui possède des propriétés comme la masse, la vitesse, et l\'énergie.\n\nEn thermodynamique, lorsque nous parlons de particules, nous considérons généralement :\n\n1. **Les molécules de gaz** : Dans un gaz, les particules sont les molécules qui se déplacent librement, entrent en collision les unes avec les autres et avec les parois du récipient.\n\n2. **L\'énergie cinétique des particules** : La température d\'un système est liée à l\'énergie cinétique moyenne des particules. Plus les particules se déplacent rapidement (en moyenne), plus la température est élevée.\n\n3. **Les interactions entre particules** : Dans les liquides et les solides, les interactions entre particules sont plus fortes que dans les gaz, ce qui explique leurs propriétés différentes.\n\nAs-tu des questions spécifiques sur le rôle des particules en thermodynamique ?'
        },
        {
            'role': 'user',
            'content': 'C\'est bon merci. Et le concept de pression ?'
        },
        {
            'role': 'assistant',
            'content': 'Super, passons à la pression alors !\n\nLa pression est une notion cruciale en thermodynamique. Elle est définie comme la force exercée par unité de surface. En termes de formule : P = F/A (Pression = Force/Aire).\n\nEn thermodynamique, la pression peut être expliquée de plusieurs façons :\n\n1. **À l\'échelle microscopique** : La pression d\'un gaz résulte des collisions des particules contre les parois du récipient. Chaque fois qu\'une particule rebondit sur une paroi, elle exerce une petite force. La somme de toutes ces collisions crée la pression que nous ressentons.\n\n2. **Relation avec les autres variables** : La pression est liée à d\'autres grandeurs thermodynamiques comme la température, le volume et la quantité de matière. C\'est ce qu\'exprime la loi des gaz parfaits : PV = nRT.\n\n3. **Importance dans les processus** : Les différences de pression sont souvent les moteurs des transformations en thermodynamique (comme dans les machines thermiques, les écoulements de fluides, etc.).\n\nAvez-vous des questions sur comment la pression intervient dans les processus thermodynamiques ?'
        },
        {
            'role': 'user',
            'content': 'Quel est le lien entre pression et température ?'
        },
        {
            'role': 'assistant',
            'content': 'Ah, excellente question ! Le lien entre la pression et la température est fondamental en thermodynamique et est souvent expliqué par la loi des gaz parfaits.\n\nVoici les principales relations entre pression et température :\n\n1. **Loi de Gay-Lussac (à volume constant)** : À volume constant, la pression d\'un gaz est proportionnelle à sa température absolue. En formule : P ∝ T (à V constant). Si on double la température absolue (en kelvin), la pression double également.\n\n2. **Explication microscopique** : Lorsque la température augmente, les particules se déplacent plus rapidement et heurtent les parois du récipient avec plus de force et plus fréquemment, ce qui augmente la pression.\n\n3. **Dans la loi des gaz parfaits** : P = nRT/V. On voit directement que P est proportionnelle à T (si n, R et V restent constants).\n\n4. **Applications pratiques** : Ce lien explique pourquoi un pneu gonflé à l\'air peut sembler dégonflé par temps froid (la pression diminue avec la température) ou pourquoi il faut être prudent avec les aérosols exposés à la chaleur (la pression augmente et peut faire exploser le contenant).\n\nY a-t-il un aspect particulier de cette relation que vous aimeriez approfondir ?'
        }
    ]
    
    for idx, msg in enumerate(messages):
        metadata = None
        if msg['role'] == 'user':
            metadata = {'user_id': student.id, 'author': 'student', 'role': 'student'}
        elif msg['role'] == 'assistant':
            metadata = {'model': 'gpt-4o-mini', 'user_id': student.id}
            
        Message.objects.create(
            thread=thread,
            role=msg['role'],
            content=msg['content'],
            message_number=idx + 1,
            metadata=metadata
        )
    print('Thermodynamics conversation messages created successfully')
"

PORT="${PORT:-8000}"

CORES=$(nproc)
WORKERS=$((CORES * 2))
if [ "$WORKERS" -lt 2 ]; then
  WORKERS=2
fi

echo "Starting Gunicorn on port $PORT with $WORKERS workers"

exec gunicorn simba.wsgi:application \
    --bind "0.0.0.0:$PORT" \
    --workers $WORKERS \
    --worker-class sync \
    --worker-connections 1000 \
    --timeout 240 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    --limit-request-line 4094 \
    --limit-request-fields 100