from django.core.management.base import BaseCommand, CommandError
from xmodule.modulestore.django import modulestore
from opaque_keys.edx.keys import CourseKey
from opaque_keys import InvalidKeyError
from opaque_keys.edx.locations import SlashSeparatedCourseKey
from lms.djangoapps.instructor.views.tools import get_student_from_identifier
from datetime import datetime
try:
    from openedx.core.djangoapps.video_evms.api import get_course_edx_val_ids
except Exception:
    raise CommandError("Failed to import EVMS api")

#
# To run from command line: ./manage.py cms evms_update course-v1:org0+akbar+run0 test --settings=devstack
# To update all courses: ./manage.py cms evms_update ALL_COURSES test --settings=devstack


class Command(BaseCommand):
    """Updates edx_course_video_id and evms_refresh from EVMS"""
    help = 'Update edx_course_video_id from evms for given course as some user'
    args = "course_key user"

    def course_key_from_arg(self, arg):
        """
        Convert the command line arg into a course key
        """
        try:
            return CourseKey.from_string(arg)
        except InvalidKeyError:
            return SlashSeparatedCourseKey.from_deprecated_string(arg)

    def add_arguments(self, parser):
        parser.add_argument('--course_key', dest='course_key')
        parser.add_argument('--user', dest='user')

    def handle(self, *args, **options):
        "Execute the command"
        if len(args) != 2:
            raise CommandError("evms_refresh requires 2 arguments: <course_id> <user>")
        store = modulestore()

        if args[0] == "ALL_COURSES":
            all_courses = store.get_courses()
            course_keys = [self.course_key_from_arg(str(course.id)) for course in all_courses]
        else:
            course_keys = [self.course_key_from_arg(args[0])]

        user = get_student_from_identifier(args[1])

        for course_key in course_keys:
            values = get_course_edx_val_ids(str(course_key))

            if not values:
                values = [{"display_name": "ERROR: failed to load list video_id from EVMS", "value": "ERROR"}]

            course = store.get_course(course_key)
            course.edx_video_id_options = values
            course.evms_refresh = str(datetime.now().replace(microsecond=0))
            course.save()
            store.update_item(course, user.id)

