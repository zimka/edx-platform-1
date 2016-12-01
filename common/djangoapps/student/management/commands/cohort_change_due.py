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
        parser.add_argument('--user', dest='user')

    def handle(self, **options):
        store = modulestore()
        self.stdout.write("Hello command world")

        who_keys = ('cohort', 'user')
        where_keys = ('problem_location', 'course_key')
        when_keys = ('days_add', 'date_set')

        who_key, who_val = self._exist_n_unique(options, who_keys)
        where_key, where_val = self._exist_n_unique(options, where_keys)
        when_key, when_val = self._exist_n_unique(options, when_keys)

        choose_keys = [who_key, where_key, when_key]
        changer_wrap = self.choose_date_changer(choose_keys)
        changer = changer_wrap(who_val, where_val, when_val, store, stdout=self.stdout)
        changer.change_due()

    @staticmethod
    def _exist_n_unique(container, keys):
        """
        Проверяет что в контейнере для одного и только одного ключа из данных
        есть not-None значение
        :return: key
        """
        exist_pairs = [(k, container[k]) for k in keys if container[k]]
        if len(exist_pairs) != 1:
            raise CommandError("""
                Non un  ique value for keys = {keys}. Ambiguous command.
                {dict}
            """.format(keys=keys, dict=exist_pairs))
        single_key = exist_pairs[0][0]
        return single_key, container[single_key]

    @staticmethod
    def choose_date_changer(keys):
        key_set = set(keys)
        if len(key_set) != 3:
            raise CommandError("Internal Error. To much keys:{}".format(keys))
        user_set_date_keys = ['user', 'date_set', 'problem_location']
        if all(x in key_set for x in user_set_date_keys):
            return UserSetProblemDate.wrap()


class DateChanger(object):
    def __init__(self, who, where, when, store, stdout=None):
        self.who = who  # user or cohort identifier
        self.when = when  # date to set or days to add
        self.where = where  # xblock or course location
        self.stdout = stdout
        self.store = store

    def set_stdout(self, stdout):
        self.stdout = stdout

    @staticmethod
    def _get_xblock_course(xblock):
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

    @classmethod
    def wrap(cls):
        def inner_wrap(*args, **kwargs):
            return cls(*args, **kwargs)
        return inner_wrap


class UserSetProblemDate(DateChanger):
    def change_due(self):
        store = self.store

        usage_key = UsageKey.from_string(self.where)
        xblock = store.get_item(usage_key)
        if not xblock:
            raise CommandError("Didn't find xblock for location {}".format(self.where))

        user = require_student_from_identifier(self.who)

        date = self._parse_date(self.when)

        course = self._get_xblock_course(xblock)
        course_key = course.id

        is_enrolled = CourseEnrollment.is_enrolled(user, course_key)
        if not is_enrolled:
            raise CommandError("User {} is not enrolled on course with key {}".format(user.username, course_key))
        set_due_date_extension(course, xblock, user, date)
