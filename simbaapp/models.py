from django.db import models


class User(models.Model):
    username = models.CharField(max_length=255, unique=True, null=False)
    email = models.EmailField(unique=True, null=False)
    password_hash = models.CharField(max_length=255, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.username
    
    def get_owned_courses_count(self):
        """Get the number of courses this user owns (as teacher)"""
        return Course.objects.filter(owner=self).count()
    
    def get_total_activities_count(self):
        """Get the total number of activities this user has created"""
        return Activity.objects.filter(owner=self).count()
    
    def get_enrolled_courses_count(self):
        """Get the number of courses this user is enrolled in (as student)"""
        return CourseEnrollment.objects.filter(user=self).count()
    
    def can_create_course(self):
        """Check if user can create a new course (limit: 3)"""
        return self.get_owned_courses_count() < 3
    
    def can_create_activity(self, course=None):
        """Check if user can create a new activity (limit: 6 per course)"""
        if course:
            course_activities_count = Activity.objects.filter(owner=self, course=course).count()
            return course_activities_count < 6
        else:
            owned_courses = Course.objects.filter(owner=self)
            for owned_course in owned_courses:
                course_activities_count = Activity.objects.filter(owner=self, course=owned_course).count()
                if course_activities_count < 6:
                    return True
            return False
    
    def can_join_course(self):
        """Check if user can join a new course (limit: 3 total including owned)"""
        total_courses = self.get_owned_courses_count() + self.get_enrolled_courses_count()
        return total_courses < 3

class Course(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="courses")
    created_at = models.DateTimeField(auto_now_add=True)
    enrollment_code = models.CharField(max_length=8, unique=True)

    def __str__(self):
        return self.title
        
    def save(self, *args, **kwargs):
        if not self.enrollment_code:
            import uuid
            self.enrollment_code = uuid.uuid4().hex[:8].upper()
        super().save(*args, **kwargs)


class CourseEnrollment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    role = models.CharField(max_length=20, choices=[('student', 'Student'), ('teacher', 'Teacher')], default='student')
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = (("user", "course"),)
        
    def __str__(self):
        return f"{self.user} as {self.role} in {self.course}"


class Activity(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="activities")
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    expert_mode = models.BooleanField(default=False)
    custom_prompt = models.TextField(blank=True, null=True)
    questions = models.JSONField(blank=True, null=True, default=list)
    agent_attitude = models.CharField(max_length=20, choices=[('friendly', 'Friendly'), ('informal', 'Informal'), ('formal', 'Formal')], default='friendly')
    subjects = models.TextField(blank=True, null=True)
    restrict_to_subject = models.BooleanField(default=False)
    allow_questions = models.BooleanField(default=True)
    allow_emojis = models.BooleanField(default=True)
    trust_document = models.BooleanField(default=True)
    word_limit = models.PositiveIntegerField(default=0)
    start_date = models.DateTimeField(blank=True, null=True)
    end_date = models.DateTimeField(blank=True, null=True)
    is_visible = models.BooleanField(default=True)
    allow_redo = models.BooleanField(default=True)
    openai_assistant_id = models.CharField(max_length=255, blank=True, null=True)
    vector_store_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.title:
            return f"{self.title} by {self.owner}"
        return f"Activity by {self.owner} on {self.course}"
    

class Thread(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="threads")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    attempt_number = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("activity", "user", "attempt_number"),)

    def __str__(self):
        return f"Thread by {self.user} on {self.activity} (Attempt {self.attempt_number})"


class Message(models.Model):
    content = models.TextField(null=False)
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=50, null=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(blank=True, null=True)
    message_number = models.PositiveIntegerField()

    class Meta:
        ordering = ['message_number']

    def __str__(self):
        return f"Message ({self.role}) at {self.timestamp}"


class Analytics(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.SET_NULL, null=True, blank=True)  
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True)
    metrics = models.JSONField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Analytics at {self.timestamp}"

class Event(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    verb = models.SmallIntegerField(choices = [(0,"Created"), (1,"Deleted"), (2,"Opened"), (3,"Closed"), (4,"Joined"), (5,"Modified")])
    object = models.SmallIntegerField(choices = [(0,"Account"), (1,"Course"), (2,"Activity"), (3,"Thread"), (4, "Message"), (5,"Simba")])
    context = models.JSONField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"subject : {self.user}, verb : {self.verb}, object : {self.object}"