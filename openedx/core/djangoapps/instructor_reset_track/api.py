from rest_framework.generics import ListAPIView
from rest_framework import permissions

from openedx.core.lib.api.authentication import OAuth2Authentication, SessionAuthentication

from .models import InstructorResetStudentAttempts
from .permissions import IsCourseStaffInstructor
from .serializers import InstructorResetStudentAttemptsSerializer, InputInstructorResetAttemptSerializer


class InstructorResetStudentAttemptsView(ListAPIView):
    """
        **Use Cases**

            Allows to get paginated instructor actions

        **Example Requests**

            GET /api/extended/instructor_reset_track/{course_key_string}

        **Response Values**

            200 - OK , 400 - bad parameters, 401 - non-staff user requests data, 403 - not authorized
    """
    paginate_by = 25
    serializer_class = InstructorResetStudentAttemptsSerializer
    authentication_classes = (OAuth2Authentication, SessionAuthentication)
    permission_classes = (permissions.IsAuthenticated, IsCourseStaffInstructor)

    def get_queryset(self):
        course_id = self.kwargs.get("course_id")
        query = InstructorResetStudentAttempts.represent_queryset(course_id)
        username = self.request.query_params.get("username")

        data_validation = InputInstructorResetAttemptSerializer(data={"username": username, "course_id": course_id})
        data_validation.is_valid(raise_exception=True)

        if username:
            query = query.filter(student_username=username)
        return query
