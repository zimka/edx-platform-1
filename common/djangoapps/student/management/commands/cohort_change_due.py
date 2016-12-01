# -*- coding: utf-8 -*-
import dateutil
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import utc
from lms.djangoapps.instructor.views.tools import require_student_from_identifier, set_due_date_extension
from openedx.core.djangoapps.course_groups.cohorts import get_cohort_by_id, get_cohort_by_name
from opaque_keys.edx.keys import CourseKey, UsageKey
from student.models import CourseEnrollment
from xmodule.modulestore.django import modulestore


class Command(BaseCommand):
    help = u"""
    Changes due date for given problem for given cohort or user
    """ + u"""
    Команде нужно указать 3 параметра: для кого менять, где менять и на когда менять
    Кто:
        --user={username / emmail},
        --cohort={name/id[ не тестировал]}
    Где:
        --problem_location={Location проблемы из STAFF DEBUG INFO в LMS}
        --course_key={id курса, например 'course-v1:test_o+test_n+test_r'}
    Когда:
        --date_set={дата формата 2017/01/31}
        --days_add={int добавить дней. Команда с этой опцией не кумулятивна.}
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

        who_keys = ('cohort', 'user')
        where_keys = ('problem_location', 'course_key')
        when_keys = ('days_add', 'date_set')

        who_key, who_val = self._exist_n_unique(options, who_keys)
        where_key, where_val = self._exist_n_unique(options, where_keys)
        when_key, when_val = self._exist_n_unique(options, when_keys)

        choose_keys = [who_key, where_key, when_key]
        changer_wrap = choose_date_changer(choose_keys)
        changer = changer_wrap(who_val, where_val, when_val, store, stdout=self.stdout)
        changer.change_due()
        self.stdout.write("Successfully changed date.")

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


def choose_date_changer(keys):
    key_set = set(keys)
    if len(key_set) != 3:
        raise CommandError("Internal Error. To much keys:{}".format(keys))

    user_problem_set_date_keys = ['user', 'date_set', 'problem_location']
    if all(x in key_set for x in user_problem_set_date_keys):
        return UserProblemSetDate.wrap()

    user_problem_add_days_keys = ['user', 'days_add', 'problem_location']
    if all(x in key_set for x in user_problem_add_days_keys):
        return UserProblemAddDays.wrap()

    user_course_set_date_keys = ['user', 'date_set', 'course_key']
    if all(x in key_set for x in user_course_set_date_keys):
        return UserCourseSetDate.wrap()

    user_course_add_days_keys = ['user', 'days_add', 'course_key']
    if all(x in key_set for x in user_course_add_days_keys):
        return UserCourseAddDays.wrap()

    cohort_problem_set_date_keys = ['cohort', 'date_set', 'problem_location']
    if all(x in key_set for x in cohort_problem_set_date_keys):
        return CohortProblemSetDate.wrap()

    cohort_problem_add_days_keys = ['cohort', 'days_add', 'problem_location']
    if all(x in key_set for x in cohort_problem_add_days_keys):
        return CohortProblemAddDays.wrap()

    cohort_course_set_date_keys = ['cohort', 'date_set', 'course_key']
    if all(x in key_set for x in cohort_course_set_date_keys):
        return CohortCourseSetDate.wrap()

    cohort_course_add_days_keys = ['cohort', 'days_add', 'course_key']
    if all(x in key_set for x in cohort_course_add_days_keys):
        return CohortCourseAddDays.wrap()

    raise NotImplementedError("Keys combination not recognized")


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

    @property
    def users_group(self):
        raise NotImplementedError

    @property
    def xblock_group(self):
        raise NotImplementedError

    @property
    def dates_group(self):
        raise NotImplementedError

    @property
    def course(self):
        raise NotImplementedError

    def change_due(self):
        for user in self.users_group:
            for num, xblock in enumerate(self.xblock_group):
                date = self.dates_group[num]

                is_enrolled = CourseEnrollment.is_enrolled(user, self.course.id)
                if not is_enrolled:
                    raise CommandError("User {} is not enrolled on course with key {}".format(
                        user.username,
                        self.course.id))

                set_due_date_extension(self.course, xblock, user, date)


class ProblemMixin(object):
    @property
    def xblock_group(self):
        try:
            return self._xblock_group
        except AttributeError:
            pass
        usage_key = UsageKey.from_string(self.where)
        xblock = self.store.get_item(usage_key)
        if not getattr(self, "_course", False):
            self._course = self._get_xblock_course(xblock)
        self._xblock_group = [xblock]

        return self._xblock_group

    @property
    def course(self):
        try:
            return self._course
        except AttributeError:
            xblock = self.xblock_group[0]
            self._course = self._get_xblock_course(xblock)
            return self._course
        raise NotImplementedError


class CourseMixin(object):
    @property
    def xblock_group(self):
        try:
            return self._xblock_group
        except AttributeError:
            pass

        course_key = CourseKey.from_string(self.where)
        course = self.store.get_course(course_key)
        if not getattr(self, "_course", False):
            self._course = course

        items = self.store.get_items(course_key)
        items = [x for x in items if (getattr(x, "due", False) and x.format)]
        self._xblock_group = items
        return self._xblock_group

    @property
    def course(self):
        try:
            return self._course
        except AttributeError:
            pass
        course_key = CourseKey.from_string(self.where)
        self._course = self.store.get_course(course_key)
        return self._course


class UserMixin(object):
    @property
    def users_group(self):
        try:
            return self._users_group
        except AttributeError:
            pass
        self._users_group = [require_student_from_identifier(self.who)]
        return self._users_group


class CohortMixin(object):
    def _get_cohort(self, cohort_id_or_name):
        course_key = self.course.id
        try:
            cohort = get_cohort_by_name(course_key,cohort_id_or_name)
            return cohort
        except Exception as e:
            pass
        try:
            cohort = get_cohort_by_id(course_key, cohort_id_or_name)
            return cohort
        except Exception as e:
            pass
        raise CommandError("Didn't find cohort")

    @property
    def users_group(self):
        try:
            return self._users_group
        except AttributeError:
            pass
        cohort = self._get_cohort(self.who)
        self._users_group = list(cohort.users.all())
        return self._users_group


class SetDateMixin(object):
    @property
    def dates_group(self):
        try:
            return self._dates_group
        except AttributeError:
            pass
        self._dates_group = [self._parse_date(self.when)]*len(self.xblock_group)
        return self._dates_group


class AddDaysMixin(object):
    """
    IMPORTANT
    При текущей реализации прибавление дней не кумулятивно -
    в качестве базы берется значение due самого xblock, а не
    StudentFieldOverride, поэтому если выполнение команды дважды
    приведет к такому же результату, как и однократное.
    """

    @property
    def dates_group(self):
        try:
            return self._dates_group
        except AttributeError:
            pass
        xblocks = self.xblock_group
        dates = [x.due for x in xblocks]
        dates = [d + timedelta(days=int(self.when)) for d in dates]
        self._dates_group = dates
        return self._dates_group


class UserProblemSetDate(UserMixin, ProblemMixin, SetDateMixin, DateChanger):
    pass


class UserProblemAddDays(UserMixin, ProblemMixin, AddDaysMixin, DateChanger):
    pass


class UserCourseSetDate(UserMixin, CourseMixin, SetDateMixin, DateChanger):
    pass


class UserCourseAddDays(UserMixin, CourseMixin, AddDaysMixin, DateChanger):
    pass


class CohortProblemSetDate(CohortMixin, ProblemMixin, SetDateMixin, DateChanger):
    pass


class CohortProblemAddDays(CohortMixin, ProblemMixin, AddDaysMixin, DateChanger):
    pass


class CohortCourseSetDate(CohortMixin, CourseMixin, SetDateMixin, DateChanger):
    pass


class CohortCourseAddDays(CohortMixin, CourseMixin, AddDaysMixin, DateChanger):
    pass



"""
python manage.py lms cohort_change_due --course_key=course-v1:test_o+test_n+test_r --days_add=30 --cohort=my_cohort
python manage.py lms cohort_change_due --course_key=course-v1:test_o+test_n+test_r --date_set=2016/12/12 --cohort=my_cohort
python manage.py lms cohort_change_due
    --problem_location=block-v1:test_o+test_n+test_r+type@problem+block@b725c8e540884a7890e0711b3f59a0aa
    --date_set="2016/12/10"
    --user=test1@test1.com

"""