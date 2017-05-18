import logging

from django.contrib.auth.models import User
from django.utils.translation import ugettext as _

from opaque_keys.edx.keys import UsageKey
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import StudentGradeOverwrite
from .utils import get_user_by_username_or_email


class StudentGradeOverwriteView(APIView):
    """
        **Use Cases**
            Allows to manage StudentGradeOverwrite

        **Example Requests**:

            GET /api/extended/student_grade_overwrite/{course_key_string}?username='name'&block_id='<block_id>'

        **Get Parameters**

            * username: User unique username.
            * block_id: location of block

        **Post Parameters**

            * username: User unique username.
            * block_id: location of block
            * grade: float value

        **Delete Parameters**

            * username: User unique username.
            * block_id: location of block

        **Response Values**

            200 - OK , 400 - bad parameters, 403 - non-staff user requests calendar for other user

    """
    def post(self,request, course_id):
        data = request.data
        block_id = data.get("block_id")
        username_or_email = data.get("username")
        grade = data.get("grade")
        if not (block_id and username_or_email and grade):
            logging.error("")
            return Response({"error": "Parameters not specified"}, status=status.HTTP_400_BAD_REQUEST)

        failed = "Block for location '{}' not found".format(block_id)
        try:
            location = UsageKey.from_string(block_id)
            failed = "User for username or email '{}' not found".format(username_or_email)
            user = get_user_by_username_or_email(username_or_email)
            failed = "Grade {} is not digital".format(grade)
            grade = float(grade)
        except:
            logging.error("Failed Grade Overwrite by '{}' ,reason:{}".format(str(request.user), failed))
            return Response({"error": "Incorrect parameters: {}".format(failed)}, status=status.HTTP_400_BAD_REQUEST)

        if str(location.course_key) != course_id: #request done not from instructor dashboard, unlikely event
            return Response({"error": "Invalid course key"}, status=status.HTTP_400_BAD_REQUEST)
        error, sgo = StudentGradeOverwrite.overwrite_student_grade(location=location, student=user, grade=grade)
        if error: #overwrite can't be done for some reason
            message = "Overwrite for user '{}' for problem '{}' by instructor '{}' failed, reason:{}".format(
                str(user), str(location), str(request.user), error
            )
            logging.error(message)
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        logging.info("Instructor '{}' overwrote student's '{}' grade for '{}': grade was changed from {} to {}".format(
            request.user.username,
            user.username,
            str(location),
            sgo.original_grade,
            sgo.current_grade
        ))
        return Response({"message": "success"})

    def get(self, request, course_id):
        data = request.query_params
        block_id = data.get("block_id")
        username = data.get("username")
        try:
            location = UsageKey.from_string(block_id)
            user = User.objects.get(username=username)
        except:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        if str(location.course_key) != course_id:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        sgo = StudentGradeOverwrite.get_overwrite(location=location, user=user)
        if not sgo: #no overwrite
            return Response()
        return Response({
            "original_grade": sgo.original_grade,
            "current_grade": sgo.current_grade
        })

    def delete(self, request, course_id):
        data = request.data
        serialized_overwrite = data.get('serialized_overwrite')
        if not serialized_overwrite:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        try:
            sgo = StudentGradeOverwrite.deserialize(serialized_overwrite)
        except Exception as e:
            message = """Failed to delete overwrite. Please refresh page and try later.
                                    If error isn't disappearing, please contact platform administrator"""
            logging.error("From '{}': failed to delete overwrite '{}', traceback:'{}'".format(
                str(request.user), serialized_overwrite, str(e)))
            return Response({"error": _(message)},status=status.HTTP_400_BAD_REQUEST)

        if sgo.course_id != course_id:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        sgo.delete()
        logging.info("Instructor '{}' deleted student's '{}' grade overwrite for '{}': original grade restored {}".format(
            request.user.username,
            sgo.user.username,
            str(sgo.location),
            sgo.original_grade,
        ))
        return Response({"message": "original grade restored:{}".format(str(sgo.original_grade))})


class StudentVerticalGradingCourseResultOverrideView(APIView): #Currently not enabled and NOT finished
    """
        **Use Cases**
            Allows to manage tudentVerticalGradingCourseResultOverride

        **Example Requests**:

            GET /api/extended/student_course_result_override/{course_key_string}?username='name'&percent='xx'

        **Get Parameters**

            * username: User unique username.

        **Post Parameters**

            * username: User unique username.
            * percent: percent to add 1-99

        **Delete Parameters**

            * username: User unique username.

        **Response Values**

            200 - OK , 400 - bad parameters, 403 - non-staff user requests calendar for other user

    """
    def post(self, request, course_id):
        data = request.data
        username_or_email = data.get("username")
        percent = data.get("grade")
        if not (username_or_email and percent):
            return Response({"error": "Parameters not specified"}, status=status.HTTP_400_BAD_REQUEST)

        failed = "User for username or email '{}' not found".format(username_or_email)
        try:
            user = get_user_by_username_or_email(username_or_email)
            failed = "Grade {} is not digital from 1 to 100".format(percent)
            percent = float(percent) / 100
            if not (0. <= percent <= 1.):
                raise ValueError
        except:
            return Response({"error": "Incorrect parameters: {}".format(failed)}, status=status.HTTP_400_BAD_REQUEST)
