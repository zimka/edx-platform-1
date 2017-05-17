from django.conf import settings
from django.conf.urls import patterns, url
from .api import StudentGradeOverwriteView


urlpatterns = patterns(
    '',
    url(r'^v1/student_grade_overwrite/{}'.format(settings.COURSE_ID_PATTERN),
        StudentGradeOverwriteView.as_view(), name='student-grade-overwrite'),
)
