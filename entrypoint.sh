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
from simbaapp.models import User, Course, Activity

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
        user=teacher
    )
    print('Default activity created successfully')
else:
    print('Default activity already exists')
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