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
        response = None

        if token != settings.CMS_PROCTORING_API_KEY:
            response = Response({"error": "Wrong api key"},
                                status=400)
        course_id = kwargs.get('course_id', None)
        if not course_id:
            response = response or Response({"error": "No course id in request"},
                                            status=400)
        course_key = CourseKey.from_string(course_id)
        store = modulestore()
        course = store.get_course(course_key)
        if not course:
            response = response or Response({"error": "No course with such course_id: '{}'".format(course_id)},
                                            status=400)
        known_providers = settings.PROCTORING_BACKEND_PROVIDERS
        if service not in known_providers:
            response = response or Response({"error": "Unknown proctoring service:{}".format(service)},
                                            status=400)
        available_providers = course.available_proctoring_services.split(',')
        if service not in available_providers:
            response = response or Response({"error": "This proctoring service is not available for course:{}".format(service)},
                                            status=400)
        try:
            int(user_id)
        except ValueError:
            answer = {"error": "Broken user_id:{}".format(user_id)}
            response = response or Response(answer,
                                            status=400)

        response = response or Response(status=200)
        code = response.status_code
        response_data = response.data or "OK"

        _log = "Proctoring api request: data '{request_data}';course_id: '{course_id}';Response:{response_data}"
        _log = _log.format(request_data=str(dict(request.data)), course_id=str(course_id), response_data=response_data)
        logging.info(_log)
        if code == 200:
            course.proctoring_service = service
            store.update_item(course, user_id)
        return response
