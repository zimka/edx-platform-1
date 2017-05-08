from django.conf import settings
from django.conf.urls import patterns, url
from .api import StudentGradeOverrideView


urlpatterns = patterns(
    '',
    url(r'^v1/student_grade_override/{}'.format(settings.COURSE_ID_PATTERN),
        StudentGradeOverrideView.as_view(), name='student-grade-override'),
)
