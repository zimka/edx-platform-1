# -*- coding: utf-8 -*-
import logging
import json

from django.http import Http404

from rest_framework import serializers
from rest_framework import status
from rest_framework.response import Response
from rest_framework.generics import ListCreateAPIView
from opaque_keys.edx.keys import CourseKey

from xmodule.modulestore.django import modulestore

from .api import create_course

log = logging.getLogger(__name__)


class CourseViewMixin(object):
    def get_course_or_404(self):
        """
        Retrieves the specified course, or raises an Http404 error if it does not exist.
        Also checks to ensure the user has permissions to view the course
        """
        try:
            course_id = self.kwargs.get('course_id')
            course_key = CourseKey.from_string(course_id)
            course = modulestore().get_course(course_key)
            self.check_course_permissions(self.request.user, course_key)

            return course
        except ValueError:
            raise Http404

    def user_can_access_course(self, user, course):
        """
        Determines if the user is staff or an instructor for the course.
        Always returns True if DEBUG mode is enabled.
        """
        return True

    def check_course_permissions(self, user, course):
        """
        Checks if the request user can access the course.
        Raises 404 if the user does not have course access.
        """
        if not self.user_can_access_course(user, course):
            raise Http404


class CourseManagement(CourseViewMixin, ListCreateAPIView):
    """
    **Варианты использования**

        Получить список курсов
        Получить информацию о курсе
        Создать курс
        Изменить информацию о курсе
        "Удалить курс" - скрыть курс из LMS, добавить аттрибут is_deleted для того, чтобы отправить курс вниз в
        списке своих курсов в Studio

    **Примеры запросов**

          GET /api/npoed_course_api/v0/courses/
          GET /api/npoed_course_api/v0/courses/{course_id}
          POST /api/npoed_course_api/v0/courses/{"mode": "create", "course_details":<dict>}
          POST /api/npoed_course_api/v0/courses/{"mode": "update", "course_details":<dict>}
          POST /api/npoed_course_api/v0/courses/{"mode": "delete", "course_details":<dict>}

    **Возврвщаемые переменные**

        * позже
    """
    serializer_class = serializers.Serializer

    def get(self, request, *args, **kwargs):
        # stub
        # TODO: code it!
        return Response(status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        available_modes = ['create', 'update', 'delete']
        data = request.DATA.copy()

        # If requested mode is not available we send 400
        if data['mode'] not in available_modes:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        course_details = data['course_details']
        if not course_details:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        course_details = json.loads(course_details.replace("'", "\""))

        # create course
        if data['mode'] == 'create':
            response_data = create_course(course_details)
            return Response(data=json.dumps(response_data), content_type="application/json")
        return Response(status=status.HTTP_204_NO_CONTENT)
