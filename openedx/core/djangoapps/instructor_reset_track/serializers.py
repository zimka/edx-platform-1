from django.contrib.auth.models import User
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
            raise serializers.ValidationError("No course with such course_id: '{}'".format(value))
        return key

    def _validate_username(self, value):
        if not value:
            return None
        try:
            user = User.objects.get(username=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("No user with such username: '{}'".format(value))
        return user

    def validate(self, data):
        key = self._validate_course_id(data.get('course_id'))
        user = self._validate_username(data.get('username'))
        if not user:
            return data
        if not CourseEnrollment.is_enrolled(user, key):
            raise serializers.ValidationError("User '{}' not enrolled in the course '{}'".format(user.username, str(key)))
        return data
