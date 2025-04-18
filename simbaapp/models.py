from django.db import models

class Institution(models.Model):
    name = models.CharField(max_length=255, null=False)
    description = models.TextField(blank=True, null=True)
    domain = models.CharField(max_length=255, blank=True, null=True)
    logo_url = models.URLField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class User(models.Model):
    username = models.CharField(max_length=255, unique=True, null=False)
    email = models.EmailField(unique=True, null=False)
    password_hash = models.CharField(max_length=255, null=False)
    role = models.CharField(max_length=50, default="student")
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.username


class UserInstitution(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE)
    role = models.CharField(max_length=50, default="member")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("user", "institution"),)
        verbose_name = "User Institution"
        verbose_name_plural = "User Institutions"

    def __str__(self):
        return f"{self.user} - {self.institution}"

class Classroom(models.Model):
    name = models.CharField(max_length=255, null=False)
    description = models.TextField(blank=True, null=True)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="classrooms")
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class ClassEnrollment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)
    role = models.CharField(max_length=50, default="student")

    class Meta:
        unique_together = (("user", "classroom"),)
        verbose_name = "Class Enrollment"
        verbose_name_plural = "Class Enrollments"

    def __str__(self):
        return f"{self.user} in {self.classroom}"


class Topic(models.Model):
    title = models.CharField(max_length=255, null=False)
    description = models.TextField(blank=True, null=True)
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    prompt = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.title


class Course(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="courses")
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True, related_name="courses")
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
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.title:
            return f"{self.title} by {self.user}"
        return f"Activity by {self.user} on {self.course}"


class Message(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE) 
    content = models.TextField(null=False)
    role = models.CharField(max_length=50, null=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(blank=True, null=True)

    def __str__(self):
        return f"Message ({self.role}) at {self.timestamp}"


class Analytics(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.SET_NULL, null=True, blank=True)  
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True)
    classroom = models.ForeignKey(Classroom, on_delete=models.SET_NULL, null=True, blank=True)
    institution = models.ForeignKey(Institution, on_delete=models.SET_NULL, null=True, blank=True)
    metrics = models.JSONField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Analytics at {self.timestamp}"
