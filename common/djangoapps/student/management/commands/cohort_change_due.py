# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import utc
from lms.djangoapps.instructor.views.tools import require_student_from_identifier, set_due_date_extension
from django.contrib.auth.models import User
import sys
import dateutil
from opaque_keys.edx.keys import CourseKey, UsageKey
from openedx.core.djangoapps.course_groups.cohorts import get_course_cohorts, get_course_cohort_settings
from xmodule.modulestore.django import modulestore, contentstore
from student.models import CourseEnrollment


class Command(BaseCommand):
    help = """
    Changes due date for given problem for given cohort or user
    """

    def add_arguments(self, parser):
        parser.add_argument('--problem_location', dest='problem_location')
        parser.add_argument('--course_key', dest='course_key')

        parser.add_argument('--days_add', dest='days_add')
        parser.add_argument('--date_set', dest='date_set')

        parser.add_argument('--cohort', dest='cohort')
        parser.add_argument('--user', dest='users')

    def handle(self, **options):
        self.store = modulestore()
        self.stdout.write("Hello command world")

        who_keys = ('cohort', 'user')
        what_keys = ('problem_location', 'course_key')
        when_keys = ('days_add', 'date_set')

        who = self._exist_n_unique(options, who_keys)
        what = self._exist_n_unique(options, what_keys)
        when = self._exist_n_unique(options, when_keys)

    def user_change_due(self, problem_location, date, user):
        store = self.store
        self.stdout.write(str(type(store)))
        usage_key = UsageKey.from_string(problem_location)

        xblock = store.get_item(usage_key)
        self.stdout.write(str(type(xblock)))
        self.stdout.write(str(xblock))
        course = self._xblock_course(xblock)
        course_key = course.id
        is_enrolled = CourseEnrollment.is_enrolled(user, course_key)
        if not is_enrolled:
            raise CommandError("User {}() is not enrolled on course with key {}".format(user.username, course_key))
        set_due_date_extension(course, xblock, user, date)

    @staticmethod
    def _exist_n_unique(container, keys):
        """
        Проверяет что в контейнере для одного и только одного ключа из данных
        есть not-None значение
        :return: key
        """
        exist_pairs = [(k, container[k]) for k in keys if container[k]]
        if len(exist_pairs) != 0:
            raise CommandError("""
                Non unique value for keys = {keys}. Ambiguous command.
                {dict}
            """.format(keys=keys, dict=exist_pairs))
        single_key = exist_pairs[0][0]
        return single_key


class DateChanger:
    def __init__(self, who, when, what, store, stdout=None):
        self.who = who  # user or cohort
        self.when = when  # date to set or days to add
        self.what = what  # xblock or course
        self.stdout = stdout
        self.store = store

    def set_stdout(self, stdout):
        self.stdout = stdout

    @staticmethod
    def _xblock_course(xblock):
        """
        Находит для данного xblock корень-course
        :param xblock:
        :return: course
        """
        item = xblock
        for _ in range(10):
            if item.category == "course":
                return item
            item = item.get_parent()
        raise CommandError("Did not find course root for xblock")

    @staticmethod
    def _parse_date(date_str):
        """
        Парсит строку-дату в объект
        :param date_str:
        :return:
        """
        try:
            date = dateutil.parser.parse(date_str).replace(tzinfo=utc)
        except ValueError:
            raise CommandError(
                "Date {} not reckognized".format(date_str)
            )
        return date


class UserSetDate(DateChanger):
    def change_due(self):
        store = self.store
        self.stdout.write(str(type(store)))
        usage_key = UsageKey.from_string(self.what)

        xblock = store.get_item(usage_key)
        course = self._xblock_course(xblock)
        course_key = course.id
        is_enrolled = CourseEnrollment.is_enrolled(self.who, course_key)
        if not is_enrolled:
            raise CommandError("User {} is not enrolled on course with key {}".format(self.who.username, course_key))
        set_due_date_extension(course, self.what, self.who, self.when)
