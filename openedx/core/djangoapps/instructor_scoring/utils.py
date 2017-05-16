from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from opaque_keys.edx.keys import CourseKey
from .models import StudentGradeOverride


def get_instructor_scoring_context(course_id):
    context = {}
    url = reverse('student-grade-override', kwargs={"course_id": course_id})
    context['student_grade_override_url'] = url
    course_key = CourseKey.from_string(course_id)
    course_overrides = StudentGradeOverride.objects.filter(student_module__course_id=course_key)
    serialize = lambda x: "{}___{}".format(str(x.student_module.student.username), str(x.student_module.module_state_key))
    course_overrides_dict = dict((serialize(x), str(x)) for x in course_overrides)
    context['course_overrides_dict'] = course_overrides_dict

    return context


def get_user_by_username_or_email(username_or_email):
    if '@' in username_or_email:
        user = User.objects.get(email=username_or_email)
    else:
        user = User.objects.get(username=username_or_email)
    return user