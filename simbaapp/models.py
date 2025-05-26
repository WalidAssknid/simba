from django.db import models


class User(models.Model):
    username = models.CharField(max_length=255, unique=True, null=False)
    email = models.EmailField(unique=True, null=False)
    password_hash = models.CharField(max_length=255, null=False)
    role = models.CharField(max_length=50, default="student")
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.username

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
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = (("user", "course"),)
        
    def __str__(self):
        return f"{self.user} in {self.course}"


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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.title:
            return f"{self.title} by {self.user}"
        return f"Activity by {self.user} on {self.course}"
    

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