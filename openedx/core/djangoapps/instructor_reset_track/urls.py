from django.conf import settings
from django.conf.urls import patterns, url
from .api import InstructorResetStudentAttemptsView

urlpatterns = patterns(
    '',
    url(r'^{}'.format(settings.COURSE_ID_PATTERN),
        InstructorResetStudentAttemptsView.as_view(), name='instructor_reset_track'),
)
