#!/usr/bin/env python3
"""
Complete Django script to import ALL CSV tables to database
Automatically generates UUIDs and maintains mappings for all relationships
"""

import os
import csv
import django
import json
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'simba.settings')
django.setup()

from simbaapp.models import User, Course, Activity, CourseEnrollment, Thread, Message

def convert_boolean(value):
    """Converts PostgreSQL boolean string to Python"""
    if value in ('t', 'true', 'True', '1'):
        return True
    elif value in ('f', 'false', 'False', '0'):
        return False
    return None

def convert_datetime(value):
    """Converts datetime string to datetime object"""
    if value and value != '\\N':
        try:
            return datetime.fromisoformat(value.replace('T', ' '))
        except:
            return None
    return None

def convert_json(value):
    """Converts JSON string to dict"""
    if value and value != '\\N':
        try:
            return json.loads(value)
        except:
            return {}
    return {}

def create_mapping_from_original():
    """Creates mapping from original UUIDs to usernames by reading the original SQL"""
    print("Creating mapping from original data...")
    
    mappings = {
        'uuid_to_username': {},
        'uuid_to_enrollment_code': {},
        'uuid_to_activity_title': {}
    }
    
    with open('simbaapp.sql', 'r', encoding='utf-8') as f:
        current_section = None
        
        for line in f:
            # Detecta seções
            if 'COPY public.simbaapp_user' in line:
                current_section = 'user'
                continue
            elif 'COPY public.simbaapp_course' in line:
                current_section = 'course'
                continue
            elif 'COPY public.simbaapp_activity' in line:
                current_section = 'activity'
                continue
            elif line.strip() == '\\.':
                current_section = None
                continue
                
            if line.strip() and current_section:
                fields = line.rstrip('\n').split('\t')
                
                if current_section == 'user' and len(fields) >= 9:
                    username = fields[0]
                    original_uuid = fields[8]  # último campo é o ID
                    mappings['uuid_to_username'][original_uuid] = username
                    
                elif current_section == 'course' and len(fields) >= 6:
                    enrollment_code = fields[3]  # enrollment_code
                    original_uuid = fields[4]   # id do curso
                    mappings['uuid_to_enrollment_code'][original_uuid] = enrollment_code
                    
                elif current_section == 'activity' and len(fields) >= 17:
                    title = fields[0] if fields[0] != '\\N' else f"Activity_{fields[16][:8]}"
                    original_uuid = fields[15]  # id da activity
                    mappings['uuid_to_activity_title'][original_uuid] = title
                    
    print(f"Mappings created:")
    print(f"  UUIDs -> usernames: {len(mappings['uuid_to_username'])}")
    print(f"  UUIDs -> enrollment_codes: {len(mappings['uuid_to_enrollment_code'])}")
    print(f"  UUIDs -> activity_titles: {len(mappings['uuid_to_activity_title'])}")
    
    return mappings

def import_users():
    """1. Import users"""
    print("\n1. Importing users...")
    
    User.objects.all().delete()
    username_to_uuid = {}
    
    with open('csv_data/simbaapp_user.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            user = User(
                username=row['username'],
                email=row['email'],
                password_hash=row['password_hash'],
                created_at=convert_datetime(row['created_at']),
                last_login=convert_datetime(row['last_login']),
                is_email_verified=convert_boolean(row['is_email_verified']),
                email_verified_at=convert_datetime(row['email_verified_at']),
                is_admin=convert_boolean(row['is_admin'])
            )
            user.save()
            username_to_uuid[row['username']] = user.id
            
    print(f"✓ Imported {len(username_to_uuid)} users")
    return username_to_uuid

def import_courses(username_to_uuid, mappings):
    """2. Import courses"""
    print("\n2. Importing courses...")
    
    Course.objects.all().delete()
    enrollment_to_uuid = {}
    fallback_user = User.objects.first()
    
    with open('csv_data/simbaapp_course.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # Find the correct owner
            old_owner_uuid = row['owner_id']
            owner_username = mappings['uuid_to_username'].get(old_owner_uuid)
            
            if owner_username and owner_username in username_to_uuid:
                owner_new_uuid = username_to_uuid[owner_username]
                owner = User.objects.get(id=owner_new_uuid)
            else:
                owner = fallback_user
                
            course = Course(
                title=row['title'],
                description=row['description'] if row['description'] != '\\N' else '',
                owner=owner,
                created_at=convert_datetime(row['created_at']),
                enrollment_code=row['enrollment_code']
            )
            course.save()
            enrollment_to_uuid[row['enrollment_code']] = course.id
            
    print(f"✓ Imported {len(enrollment_to_uuid)} courses")
    return enrollment_to_uuid

def import_activities(username_to_uuid, enrollment_to_uuid, mappings):
    """3. Import activities (creates individual courses for orphan activities)"""
    print("\n3. Importing activities...")
    
    Activity.objects.all().delete()
    activity_title_to_uuid = {}
    fallback_user = User.objects.first()
    
    print("   Creating individual courses for orphan activities...")
    
    with open('csv_data/simbaapp_activity.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # Find owner
            old_owner_uuid = row['owner_id']
            owner_username = mappings['uuid_to_username'].get(old_owner_uuid)
            owner = User.objects.filter(id=username_to_uuid.get(owner_username)).first() or fallback_user
            
            activity_title = row['title'] if row['title'] != '\\N' else f"Activity_{row['created_at'][:10]}"
            
            # Find course
            old_course_uuid = row['course_id']
            course_enrollment_code = mappings['uuid_to_enrollment_code'].get(old_course_uuid)
            course = Course.objects.filter(id=enrollment_to_uuid.get(course_enrollment_code)).first()
            
            # If course not found, create an individual course for this activity
            if not course:
                course_title = f"Course for {activity_title}"
                course_description = f"Auto-generated course for activity: {activity_title}"
                
                # Check if a course with this title already exists
                existing_course = Course.objects.filter(title=course_title, owner=owner).first()
                if existing_course:
                    course = existing_course
                else:
                    print(f"     Creating individual course: {course_title} (owner: {owner.username})")
                    course = Course.objects.create(
                        title=course_title,
                        description=course_description,
                        owner=owner,
                        created_at=convert_datetime(row['created_at'])
                    )
                    
                    # Create automatic enrollment for the owner
                    CourseEnrollment.objects.get_or_create(
                        user=owner,
                        course=course,
                        defaults={'role': 'teacher', 'joined_at': course.created_at}
                    )
            
            activity = Activity(
                title=activity_title,
                description=row['description'] if row['description'] != '\\N' else '',
                expert_mode=convert_boolean(row['expert_mode']),
                custom_prompt=row['custom_prompt'] if row['custom_prompt'] != '\\N' else None,
                start_date=convert_datetime(row['start_date']),
                end_date=convert_datetime(row['end_date']),
                is_visible=convert_boolean(row['is_visible']),
                allow_redo=convert_boolean(row['allow_redo']),
                ai_model=row['ai_model'],
                openai_assistant_id=row['openai_assistant_id'] if row['openai_assistant_id'] != '\\N' else None,
                vector_store_id=row['vector_store_id'] if row['vector_store_id'] != '\\N' else None,
                options=convert_json(row['options']),
                created_at=convert_datetime(row['created_at']),
                updated_at=convert_datetime(row['updated_at']),
                course=course,
                owner=owner
            )
            activity.save()
            activity_title_to_uuid[activity_title] = activity.id
            
    print(f"✓ Imported {len(activity_title_to_uuid)} activities with appropriate courses")
    return activity_title_to_uuid

def import_enrollments(username_to_uuid, enrollment_to_uuid, mappings):
    """4. Import enrollments"""
    print("\n4. Importing enrollments...")
    
    CourseEnrollment.objects.all().delete()
    count = 0
    
    # 1. First create automatic enrollments for course owners (as teacher)
    print("  Creating automatic enrollments for course owners...")
    for course in Course.objects.all():
        enrollment = CourseEnrollment(
            user=course.owner,
            course=course,
            role='teacher',
            joined_at=course.created_at
        )
        try:
            enrollment.save()
            count += 1
        except:
            pass  # Ignore duplicates
    
    # 2. Import original enrollments from SQL file
    print("  Importing original enrollments...")
    with open('simbaapp.sql', 'r', encoding='utf-8') as f:
        in_enrollment_section = False
        
        for line in f:
            if 'COPY public.simbaapp_courseenrollment' in line:
                in_enrollment_section = True
                continue
            elif line.strip() == '\\.':
                if in_enrollment_section:
                    break
                in_enrollment_section = False
                continue
                
            if in_enrollment_section and line.strip():
                fields = line.rstrip('\n').split('\t')
                if len(fields) >= 5:
                    role = fields[0]
                    joined_at = convert_datetime(fields[1])
                    # fields[2] é o id do enrollment (ignoramos)
                    old_user_uuid = fields[3]    # user_id
                    old_course_uuid = fields[4]  # course_id
                    
                    # Skip if user_id or course_id are NULL
                    if old_user_uuid == '\\N' or old_course_uuid == '\\N':
                        continue
                    
                    # Map user
                    user_username = mappings['uuid_to_username'].get(old_user_uuid)
                    user = User.objects.filter(id=username_to_uuid.get(user_username)).first()
                    
                    # Map course
                    course_enrollment_code = mappings['uuid_to_enrollment_code'].get(old_course_uuid)
                    course = Course.objects.filter(id=enrollment_to_uuid.get(course_enrollment_code)).first()
                    
                    if user and course:
                        enrollment = CourseEnrollment(
                            user=user,
                            course=course,
                            role=role,
                            joined_at=joined_at
                        )
                        try:
                            enrollment.save()
                            count += 1
                        except:
                            pass  # Ignore duplicates
            
    print(f"✓ Imported {count} enrollments (owners + originals)")

def import_threads(username_to_uuid, activity_title_to_uuid, mappings):
    """5. Import threads (with more robust mapping)"""
    print("\n5. Importing threads...")
    
    Thread.objects.all().delete()
    thread_mapping = {}
    fallback_user = User.objects.first()
    
    # Counter for debugging
    successful_mappings = 0
    failed_mappings = 0
    
    with open('simbaapp.sql', 'r', encoding='utf-8') as sql_f:
        in_thread_section = False
        
        for line in sql_f:
            if 'COPY public.simbaapp_thread' in line:
                in_thread_section = True
                continue
            elif line.strip() == '\\.':
                if in_thread_section:
                    break
                in_thread_section = False
                continue
                
            if in_thread_section and line.strip():
                fields = line.rstrip('\n').split('\t')
                if len(fields) >= 6:
                    old_thread_uuid = fields[3]  # id
                    old_user_uuid = fields[4]   # user_id  
                    old_activity_uuid = fields[5]  # activity_id
                    
                    # Skip if activity_id is NULL
                    if old_activity_uuid == '\\N':
                        continue
                    
                    # Map user
                    user_username = mappings['uuid_to_username'].get(old_user_uuid)
                    user = User.objects.filter(id=username_to_uuid.get(user_username)).first()
                    
                    # Map activity more robustly
                    activity_title = mappings['uuid_to_activity_title'].get(old_activity_uuid)
                    activity = Activity.objects.filter(id=activity_title_to_uuid.get(activity_title)).first()
                    
                    # If activity not found by title, try to find by owner
                    if not activity and user:
                        print(f"     Activity not found by title '{activity_title}', searching by owner {user.username}")
                        # Search for any activity of the user (title might have changed)
                        activity = Activity.objects.filter(owner=user).first()
                        
                        # If still not found, create an activity for this user
                        if not activity:
                            course_title = f"Personal Course - {user.username}"
                            course, created = Course.objects.get_or_create(
                                title=course_title,
                                owner=user,
                                defaults={
                                    'description': f'Auto-generated personal course for {user.username}',
                                    'created_at': convert_datetime(fields[1])
                                }
                            )
                            
                            if created:
                                print(f"       Creating personal course: {course_title}")
                                # Create enrollment
                                CourseEnrollment.objects.get_or_create(
                                    user=user,
                                    course=course,
                                    defaults={'role': 'teacher', 'joined_at': course.created_at}
                                )
                            
                            activity_title_safe = activity_title or f"Activity_{old_thread_uuid[:8]}"
                            activity = Activity.objects.create(
                                title=activity_title_safe,
                                description=f"Auto-generated activity for {user.username}",
                                course=course,
                                owner=user,
                                created_at=convert_datetime(fields[1]),
                                updated_at=convert_datetime(fields[0])
                            )
                            print(f"       Creating activity: {activity_title_safe}")
                    
                    if user and activity:
                        thread = Thread(
                            activity=activity,
                            user=user,
                            attempt_number=int(fields[2]) if fields[2].isdigit() else 1,
                            updated_at=convert_datetime(fields[0]),
                            created_at=convert_datetime(fields[1])
                        )
                        
                        try:
                            thread.save()
                            thread_mapping[old_thread_uuid] = thread.id
                            successful_mappings += 1
                        except Exception as e:
                            print(f"       Error creating thread: {e}")
                            failed_mappings += 1
                    else:
                        failed_mappings += 1
                        if not user:
                            print(f"     User not found for thread {old_thread_uuid}")
                        if not activity:
                            print(f"     Activity not found for thread {old_thread_uuid}")
                            
    print(f"✓ Threads imported: {successful_mappings} success, {failed_mappings} failures")
    return thread_mapping

def normalize_message_role(role):
    """Normalizes message roles to current system format"""
    if not role or role == '\\N':
        return 'user'  # default
    
    role = role.lower().strip()
    
    # Convert student roles to 'user'
    if role in ['student', 'user', 'human', 'person']:
        return 'user'
    # Assistant/model roles
    elif role in ['assistant', 'bot', 'ai', 'system', 'simba', 'model']:
        return 'assistant'
    # For any other role, assume it's from user
    else:
        print(f"  Warning: Unknown role '{role}' converted to 'user'")
        return 'user'

def import_messages(thread_mapping):
    """6. Import messages (no fallbacks - only messages with valid threads)"""
    print("\n6. Importing messages...")
    
    Message.objects.all().delete()
    
    with open('simbaapp.sql', 'r', encoding='utf-8') as f:
        in_message_section = False
        count = 0
        role_conversions = {}
        
        for line in f:
            if 'COPY public.simbaapp_message' in line:
                in_message_section = True
                continue
            elif line.strip() == '\\.':
                if in_message_section:
                    break
                in_message_section = False
                continue
                
            if in_message_section and line.strip():
                fields = line.rstrip('\n').split('\t')
                if len(fields) >= 7:
                    content = fields[0]
                    original_role = fields[1]
                    normalized_role = normalize_message_role(original_role)
                    timestamp = convert_datetime(fields[2])
                    metadata = convert_json(fields[3]) if fields[3] != '\\N' else None
                    message_number = int(fields[4]) if fields[4].isdigit() else 1
                    old_thread_uuid = fields[6]  # thread_id
                    
                    # Track role conversions
                    if original_role != normalized_role:
                        if original_role not in role_conversions:
                            role_conversions[original_role] = 0
                        role_conversions[original_role] += 1
                    
                    thread = Thread.objects.filter(id=thread_mapping.get(old_thread_uuid)).first()
                    
                    # If mapped thread not found, skip this message -- this is because of the previous problem
                    if not thread:
                        print(f"      Warning: Thread not found for message, skipping (thread_id: {old_thread_uuid})")
                        continue
                    
                    message = Message(
                        content=content,
                        thread=thread,
                        role=normalized_role,  # Use normalized role
                        timestamp=timestamp,
                        metadata=metadata,
                        message_number=message_number
                    )
                    
                    try:
                        message.save()
                        count += 1
                    except:
                        pass
        
        # Show role conversions performed
        if role_conversions:
            print("  Role conversions performed:")
            for original_role, count_converted in role_conversions.items():
                normalized = normalize_message_role(original_role)
                print(f"    '{original_role}' -> '{normalized}': {count_converted} messages")
                        
    print(f"✓ Imported {count} messages")

def main():
    print("=== COMPLETE IMPORT OF ALL TABLES ===")
    
    try:
        # Create mappings from original data
        mappings = create_mapping_from_original()
        
        # 1. Users (independent)
        username_to_uuid = import_users()
        
        # 2. Courses (depends on users)
        enrollment_to_uuid = import_courses(username_to_uuid, mappings)
        
        # 3. Activities (depends on users and courses)
        activity_title_to_uuid = import_activities(username_to_uuid, enrollment_to_uuid, mappings)
        
        # 4. Enrollments (depends on users and courses)
        import_enrollments(username_to_uuid, enrollment_to_uuid, mappings)
        
        # 5. Threads (depends on users and activities)
        thread_mapping = import_threads(username_to_uuid, activity_title_to_uuid, mappings)
        
        # 6. Messages (depends on threads)
        import_messages(thread_mapping)
        
        print("\n=== COMPLETE IMPORT FINISHED! ===")
        print(f"Users: {User.objects.count()}")
        print(f"Courses: {Course.objects.count()}")
        print(f"Activities: {Activity.objects.count()}")
        print(f"Enrollments: {CourseEnrollment.objects.count()}")
        print(f"Threads: {Thread.objects.count()}")
        print(f"Messages: {Message.objects.count()}")
        
    except Exception as e:
        print(f"Error during import: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main() 