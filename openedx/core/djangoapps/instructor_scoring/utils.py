from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse

from opaque_keys.edx.keys import CourseKey
from .models import StudentGradeOverwrite


def get_instructor_scoring_context(course_id):
    context = {}
    if not settings.FEATURES.get("ENABLE_STUDENT_GRADE_OVERWRITE"):
        return context
    url = reverse('student-grade-overwrite', kwargs={"course_id": course_id})
    context['student_grade_overwrite_url'] = url
    course_overwrites = StudentGradeOverwrite.get_course_overwrites(course_id)
    nice_view = lambda x: x if len(x) < 80 else x[:77] + "..."
    course_overwrites_dict = dict((StudentGradeOverwrite.serialize(x), nice_view(str(x))) for x in course_overwrites)

    context['course_overwrite_dict'] = course_overwrites_dict
    sections = collect_course_sections(course_id)
    context['course_result_override_sections'] = sections
    context['enable_course_result_overwrite'] = settings.FEATURES.get('ENABLE_COURSE_RESULT_OVERWRITE')
    return context


def collect_course_sections(course_id):
    if settings.FEATURES.get('ENABLE_COURSE_RESULT_OVERWRITE'):
        raise NotImplementedError("Course result overwrite is too hacky and can be replace by certs white list")
    return {}


def get_user_by_username_or_email(username_or_email):
    if '@' in username_or_email:
        user = User.objects.get(email=username_or_email)
    else:
        user = User.objects.get(username=username_or_email)
    return user