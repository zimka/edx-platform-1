from django.contrib import admin
from .models import SuspiciousExamAttempt


class SuspiciousExamAttemptForm(admin.ModelAdmin):
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
        return exam_session_set.pretty_repr()
    sessions.short_description = "Seen sessions"

admin.site.register(SuspiciousExamAttempt, SuspiciousExamAttemptForm)
