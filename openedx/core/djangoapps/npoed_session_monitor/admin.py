from django.contrib import admin
from .models import SuspiciousExamAttempt

# TODO: Currently admin view is not only ugly, but totally unreadable and useless
admin.site.register(SuspiciousExamAttempt)
