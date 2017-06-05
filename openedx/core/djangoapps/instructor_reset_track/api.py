from rest_framework.generics import ListAPIView
from rest_framework import permissions

from openedx.core.lib.api.authentication import OAuth2Authentication, SessionAuthentication

from .models import InstructorResetStudentAttempts
from .permissions import IsCourseStaffInstructor
from .serializers import InstructorResetStudentAttemptsSerializer


class InstructorResetStudentAttemptsView(ListAPIView):
    """
        **Use Cases**

            Allows to get paginated instructor actions

        **Example Requests**

            GET /api/extended/instructor_reset_track/{course_key_string}

        **Response Values**

            200 - OK , 400 - bad parameters, 401 - non-staff user requests data
    """
    paginate_by = 5
    serializer_class = InstructorResetStudentAttemptsSerializer
    authentication_classes = (OAuth2Authentication, SessionAuthentication)
    permission_classes = (permissions.IsAuthenticated, IsCourseStaffInstructor,)

    def get_queryset(self):
        course_id = self.kwargs.get("course_id")
        return InstructorResetStudentAttempts.represent_queryset(course_id)
