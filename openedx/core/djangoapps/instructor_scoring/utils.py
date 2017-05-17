from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse

from opaque_keys.edx.keys import CourseKey
from .models import StudentGradeOverwrite


def get_instructor_scoring_context(course_id):
    context = {}
    url = reverse('student-grade-overwrite', kwargs={"course_id": course_id})
    context['student_grade_overwrite_url'] = url
    course_key = CourseKey.from_string(course_id)
    course_overwrites = StudentGradeOverwrite.objects.filter(student_module__course_id=course_key)
    serialize = lambda x: "{}___{}".format(str(x.student_module.student.username), str(x.student_module.module_state_key))
    course_overwrites_dict = dict((serialize(x), str(x)) for x in course_overwrites)
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