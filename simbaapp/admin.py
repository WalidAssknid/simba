from django.contrib import admin

from . import models


@admin.register(models.User)
class UserAdmin(admin.ModelAdmin):
	list_display = (
		"username",
		"email",
		"is_email_verified",
		"is_admin",
		"created_at",
		"last_login",
	)
	list_filter = ("is_email_verified", "is_admin", "created_at")
	search_fields = ("username", "email")
	ordering = ("-created_at",)


@admin.register(models.Course)
class CourseAdmin(admin.ModelAdmin):
	list_display = ("title", "owner", "enrollment_code", "created_at")
	search_fields = ("title", "enrollment_code", "owner__username")
	list_filter = ("created_at",)
	autocomplete_fields = ("owner",)


@admin.register(models.CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
	list_display = ("user", "course", "role", "joined_at")
	list_filter = ("role", "joined_at")
	search_fields = ("user__username", "course__title")
	autocomplete_fields = ("user", "course")


@admin.register(models.Activity)
class ActivityAdmin(admin.ModelAdmin):
	list_display = (
		"title",
		"course",
		"owner",
		"ai_model",
		"is_visible",
		"allow_redo",
		"created_at",
	)
	list_filter = ("ai_model", "is_visible", "allow_redo", "created_at")
	search_fields = ("title", "course__title", "owner__username")
	autocomplete_fields = ("course", "owner")


@admin.register(models.Thread)
class ThreadAdmin(admin.ModelAdmin):
	list_display = ("activity", "user", "attempt_number", "updated_at", "created_at")
	list_filter = ("attempt_number", "updated_at", "created_at")
	search_fields = ("activity__title", "user__username")
	autocomplete_fields = ("activity", "user")


@admin.register(models.Message)
class MessageAdmin(admin.ModelAdmin):
	list_display = ("thread", "role", "message_number", "timestamp")
	list_filter = ("role", "timestamp")
	search_fields = ("content", "thread__activity__title", "thread__user__username")
	autocomplete_fields = ("thread",)


@admin.register(models.Analytics)
class AnalyticsAdmin(admin.ModelAdmin):
	list_display = ("activity", "user", "course", "timestamp")
	list_filter = ("timestamp",)
	search_fields = ("activity__title", "user__username", "course__title")
	autocomplete_fields = ("activity", "user", "course")


@admin.register(models.Event)
class EventAdmin(admin.ModelAdmin):
	list_display = ("user", "verb", "object", "timestamp")
	list_filter = ("verb", "object", "timestamp")
	search_fields = ("user__username",)


@admin.register(models.ChainlitSession)
class ChainlitSessionAdmin(admin.ModelAdmin):
	list_display = (
		"session_id",
		"activity",
		"user",
		"thread",
		"created_at",
		"expires_at",
		"is_consumed",
	)
	list_filter = ("is_consumed", "created_at", "expires_at")
	search_fields = ("session_id", "user__username", "activity__title")
	autocomplete_fields = ("activity", "user", "thread")


@admin.register(models.EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
	list_display = ("user", "token", "is_used", "expires_at", "created_at")
	list_filter = ("is_used", "created_at", "expires_at")
	search_fields = ("user__email", "token")
	autocomplete_fields = ("user",)


@admin.register(models.PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
	list_display = ("user", "token", "is_used", "expires_at", "created_at")
	list_filter = ("is_used", "created_at", "expires_at")
	search_fields = ("user__email", "token")
	autocomplete_fields = ("user",)


@admin.register(models.InviteToken)
class InviteTokenAdmin(admin.ModelAdmin):
	list_display = ("token", "course", "role", "created_by", "is_active", "expires_at")
	list_filter = ("role", "is_active", "expires_at")
	search_fields = ("token", "course__title", "created_by__username")
	autocomplete_fields = ("course", "created_by")


@admin.register(models.ActivityToken)
class ActivityTokenAdmin(admin.ModelAdmin):
	list_display = ("token", "activity", "created_by", "is_active", "expires_at")
	list_filter = ("is_active", "expires_at")
	search_fields = ("token", "activity__title", "created_by__username")
	autocomplete_fields = ("activity", "created_by")

