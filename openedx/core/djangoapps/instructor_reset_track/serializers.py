from django.contrib.auth.models import User
from django.utils.translation import ugettext as _
from rest_framework import serializers

from opaque_keys.edx.keys import CourseKey
from student.models import CourseEnrollment

from .models import InstructorResetStudentAttempts


class InstructorResetStudentAttemptsSerializer(serializers.ModelSerializer):
    """
    Serializes instructor reset attempts
    """

    class Meta:
        model = InstructorResetStudentAttempts
        fields = ('instructor_username',
                  'student_username',
                  'block_id',
                  'action',
                  'removed_answer',
                  'time_readable',
                  'block_url',
                  )


class InputInstructorResetAttemptSerializer(serializers.Serializer):
    """
    Validates viewset input
    """
    course_id = serializers.CharField(max_length=255)
    username = serializers.CharField(max_length=50, allow_null=True, allow_blank=True)

    def _validate_course_id(self, value):
        try:
            key = CourseKey.from_string(value)
        except:
            raise serializers.ValidationError(_("{course_id} is not a valid course key.").format(
                course_id=str(value)
            ))
        return key

    def _validate_username(self, value):
        if not value:
            return None
        try:
            user = User.objects.get(username=value)
        except User.DoesNotExist:
            raise serializers.ValidationError(_("No user with that username") + u": '{}'".format(value))
        return user

    def validate(self, data):
        key = self._validate_course_id(data.get('course_id'))
        user = self._validate_username(data.get('username'))
        if not user:
            return data
        if not CourseEnrollment.is_enrolled(user, key):
            message =_("User {username} is not enrolled in the course {course_key}")
            raise serializers.ValidationError(message.format(username=user.username, course_key=str(key)))
        return data
