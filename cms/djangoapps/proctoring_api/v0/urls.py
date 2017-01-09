"""
Proctoring API v0 URI specification
"""
from django.conf import settings
from django.conf.urls import patterns, url

from proctoring_api.v0 import views


COURSE_ID_PATTERN = settings.COURSE_ID_PATTERN

urlpatterns = patterns(
    '',
    url(r'^course/{}/$'.format(COURSE_ID_PATTERN), views.CourseProctoringProvider.as_view()),
)