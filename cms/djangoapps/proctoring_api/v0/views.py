import logging

from django.conf import settings
from rest_framework.response import Response
from rest_framework.generics import UpdateAPIView

from xmodule.modulestore.django import modulestore
from opaque_keys.edx.keys import CourseKey


class CourseProctoringProvider(UpdateAPIView):
    def update(self, request, *args, **kwargs):
        token = request.data['token']
        user_id = request.data['user']
        service = request.data['service']

        if token != settings.CMS_PROCTORING_API_KEY:
            return Response({"error":"Wrong key"},
                            status=401)
        course_id = kwargs.get('course_id', None)
        if not course_id:
            return Response(status=400)

        course_key = CourseKey.from_string(course_id)
        store = modulestore()
        course = store.get_course(course_key)
        if not course:
            return Response({"error":"No course with such course_id"},
                            status=400)
        available_providers = course.available_proctoring_services.split(',')
        if service not in available_providers:
            return Response({"error":"This proctoring service is not available"},
                            status=403)
        course.proctoring_service = service
        try:
            int(user_id)
        except ValueError:
            return Response({"error": "Broken user_id"},
                            status=400)

        store.update_item(course, user_id)
        logging.info("Proctoring set from lms:'{}' by user with id: '{}'".format(service, user_id))
        return Response(status=200)
