from django.conf import settings
from django.contrib import admin
from .models import SuspiciousExamAttempt


class SuspiciousExamAttemptForm(admin.ModelAdmin):
    """
    Admin Form. Show info about suspicious attempts.
    """
    list_display = ("exam_id", "username")
    readonly_fields = ("exam_id", "username", "sessions")
    exclude = ("exam_attempt", "exam_sessions")
    list_select_related = ('exam_attempt', )

    def exam_id(self, obj):
        return str(obj.exam_attempt.proctored_exam.content_id)
    exam_id.short_description = "Exam ID"

    def username(self, obj):
        return str(obj.exam_attempt.user.username)
    username.short_description = "Username"

    def sessions(self, obj):
        exam_session_set = obj.exam_sessions
        return "\n".join(exam_session_set.pretty_repr())
    sessions.short_description = "Seen sessions"

if settings.FEATURES.get("ENABLE_SUSPICIOUS_MONITOR", False) and settings.FEATURES.get("ENABLE_SUSPICIOUS_MONITOR_ADMIN", False):
    admin.site.register(SuspiciousExamAttempt, SuspiciousExamAttemptForm)
