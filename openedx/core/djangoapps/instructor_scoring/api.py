import logging

from django.contrib.auth.models import User
from opaque_keys.edx.keys import UsageKey
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import StudentGradeOverride


class StudentGradeOverrideView(APIView):
    """
        **Use Cases**
            Allows to manage StudentGradeOverride

        **Example Requests**:

            GET /api/extended/student_grade_override/{course_key_string}?username='name'&block_id='<block_id>'

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
            return Response({"error": "Parameters not specified"}, status=status.HTTP_400_BAD_REQUEST)

        failed = "Block for location '{}' not found".format(block_id)
        try:
            location = UsageKey.from_string(block_id)
            failed = "User for username or email '{}' not found".format(username_or_email)
            if '@' in username_or_email:
                user = User.objects.get(email=username_or_email)
            else:
                user = User.objects.get(username=username_or_email)
            failed = "Grade {} is not digital".format(grade)
            grade = float(grade)
        except:
            return Response({"error": "Incorrect parameters: {}".format(failed)}, status=status.HTTP_400_BAD_REQUEST)
        if str(location.course_key) != course_id:
            return Response({"error": "Invalid course key"}, status=status.HTTP_400_BAD_REQUEST)
        error, sgo = StudentGradeOverride.override_student_grade(location=location, student=user, grade=grade)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
        logging.info("Instructor '{}' overrode student's '{}' grade for '{}': grade was changed from {} to {}".format(
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
        sgo = StudentGradeOverride.get_override(location=location, user=user)
        if not sgo:
            return Response({})
        return Response({
            "original_grade": sgo.original_grade,
            "current_grade": sgo.current_grade
        })

    def delete(self, request, course_id):
        data = request.data
        block_id = data.get("block_id")
        username = data.get("username")
        try:
            location = UsageKey.from_string(block_id)
            user = User.objects.get(username=username)
        except:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        if str(location.course_key) != course_id:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        sgo = StudentGradeOverride.get_override(location=location, user=user)
        if not sgo:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        sgo.delete()
        logging.info("Instructor '{}' deleted student's '{}' grade override for '{}': original grade restored {}".format(
            request.user.username,
            user.username,
            str(location),
            sgo.original_grade,
        ))
        return Response({"message": "original grade restored:{}".format(str(sgo.original_grade))})


class StudentVerticalGradingCourseResultOverrideView(APIView):
    pass