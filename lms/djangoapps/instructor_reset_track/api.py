import logging

from rest_framework.generics import ListAPIView

from .models import InstructorResetStudentAttempts
from .serializers import InstructorResetStudentAttemptsSerializer


class InstructorResetStudentAttemptsView(ListAPIView):
    """
        **Use Cases**
            Allows to get paginated instructor actions
        **Example Requests**:
            GET /api/extended/instructor_reset_track/{course_key_string}

        **Response Values**
            200 - OK , 400 - bad parameters, 403 - non-staff user requests calendar for other user
    """
    paginate_by = 5
    serializer_class = InstructorResetStudentAttemptsSerializer

    def get_queryset(self):
        course_id = self.kwargs['course_id']
        return InstructorResetStudentAttempts.objects.filter(success=True, course_id=course_id).order_by('-timestamp')
