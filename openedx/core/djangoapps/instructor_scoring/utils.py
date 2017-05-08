from django.core.urlresolvers import reverse
from opaque_keys.edx.keys import CourseKey
from .models import StudentGradeOverride


def get_instructor_scoring_context(course_id):
    context = {}
    url = reverse('student-grade-override', kwargs={"course_id": course_id})
    context['student_grade_override_url'] = url
    course_key = CourseKey.from_string(course_id)
    course_overrides = StudentGradeOverride.objects.filter(student_module__course_id=course_key)
    course_overrides_dict = dict((str(x.id), str(x)) for x in course_overrides)
    context['course_overrides_dict'] = course_overrides_dict
    return context

