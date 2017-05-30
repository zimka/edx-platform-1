from rest_framework import serializers
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
                  'timestamp'
                  )
