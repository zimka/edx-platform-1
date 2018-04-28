from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework import permissions

from student.roles import CourseInstructorRole, CourseStaffRole


class IsCourseStaffInstructor(permissions.BasePermission):
    def has_permission(self, request, view):
        course_id = view.kwargs.get('course_id')
        if not course_id:
            return False
        try:
            course_key = CourseKey.from_string(course_id)
        except InvalidKeyError:
            return False

        return (hasattr(request, 'user') and
                (CourseInstructorRole(course_key).has_user(request.user) or
                 CourseStaffRole(course_key).has_user(request.user)))
