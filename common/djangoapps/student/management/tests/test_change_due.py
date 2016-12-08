"""
Tests for change_due command
"""

from datetime import datetime
from datetime import timedelta
import logging
from xmodule.modulestore.tests.django_utils import TEST_DATA_MIXED_MODULESTORE
from django.core.management import call_command

from courseware.student_field_overrides import get_override_for_user
from openedx.core.djangoapps.course_groups.tests.helpers import CohortFactory
from openedx.core.djangoapps.course_groups.cohorts import CohortMembership
from student.models import CourseEnrollment
from student.tests.factories import UserFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory
from opaque_keys.edx.keys import CourseKey, UsageKey


class TestChangeDue(ModuleStoreTestCase):
    """
    Test for change_due command
    """

    MODULESTORE = TEST_DATA_MIXED_MODULESTORE

    def setUp(self):
        """
        Course with graded and not graded problems, with two cohorts and users without cohorts
        """
        super(TestChangeDue, self).setUp()
        self.course = CourseFactory(start=self.days_ago(14), publish_item=True)
        self.chapter = ItemFactory.create(parent_location=self.course.location,
                                          category='chapter',
                                          start=self.days_ago(10),
                                          publish_item=True,
                                          )

        self.sequential = ItemFactory.create(parent_location=self.chapter.location,
                                             category='sequential',
                                             start=self.days_ago(30),
                                             publish_item=True,
                                             format="Homework",
                                             graded=True,
                                             due=self.days_ago(14)
                                             )

        self.sequential2 = ItemFactory.create(parent_location=self.chapter.location,
                                              category='sequential',
                                              start=self.days_ago(20),
                                              publish_item=True,
                                              )

        homework = self.set_task(n_task=1)[0]
        ungraded = self.set_task(n_task=1, parent_location=self.sequential2.location)[0]
        n_problems = 2
        self.set_task(n_task=n_problems,
                      category_task="problem",
                      parent_location=homework.location,
                      due=True
                      )
        self.set_task(n_task=n_problems,
                      category_task="problem",
                      parent_location=ungraded.location
                      )

        n_users = 2
        self.cohorted_users = [UserFactory() for _ in range(n_users)]
        self.uncohorted_users = [UserFactory() for _ in range(n_users)]
        self.other_cohorted_users = [UserFactory() for _ in range(n_users)]
        self.users = self.cohorted_users + self.uncohorted_users + self.other_cohorted_users
        for u in self.users:
            CourseEnrollment.enroll(u, self.course.id)

        self.cohort = CohortFactory(course_id=self.course.id, name="tested_cohort")
        self.other_cohort = CohortFactory(course_id=self.course.id, name="other_cohort")

        for u in self.cohorted_users:
            membership = CohortMembership(course_user_group=self.cohort, user=u)
            membership.save()

        for u in self.other_cohorted_users:
            membership = CohortMembership(course_user_group=self.other_cohort, user=u)
            membership.save()
        self.now = datetime.now()

    @property
    def problems(self):
        items = self.store.get_items(self.course.id)
        problems = [i for i in items if i.category == "problem"]
        return problems

    @property
    def graded_problems(self):
        return [i for i in self.problems if i.graded]

    @property
    def ungraded_problems(self):
        return [i for i in self.problems if not i.graded]

    def test_all_cant_answer(self):
        "Check that nobody can vote before change_due"
        problems = self.problems
        users = self.users
        now = datetime.now()
        blocks_users_can_answer = self.write_down_can_answer_results(blocks=problems, users=users)

        for user in users:
            for block in problems:
                value = blocks_users_can_answer[block.location][user.username]
                check = (value is None) or (value is False)
                print(user.username, block.display_name, self.block_user_date(block, user), value, check)
                self.assertTrue(check, msg="{user},{problem}: date:{date}".format(
                    user=user.username,
                    problem=block.display_name,
                    date=self.block_user_date(block, user))
                                )

    def test_user_setdate_block(self):
        problems = self.problems
        users = self.users

        selected_user = users[0]
        selected_block = self.graded_problems[0]
        before = self.write_down_can_answer_results(blocks=problems, users=users)
        future = datetime.now() + timedelta(days=10)
        set_date = "{year}/{month}/{day}".format(year=future.year, month=future.month, day=future.day)
        print(selected_user.username, selected_block.location, set_date)

        key_cycle = lambda x: self.store.get_item(UsageKey.from_string(str(x.location)))
        """
        TODO: key_cycle doesn't work in test env, but works in devstack env;

        File "/edx/app/edxapp/edx-platform/common/djangoapps/student/management/tests/test_change_due.py", line 141, in test_user_setdate_block
        set_date=set_date
        File "/edx/app/edxapp/venvs/edxapp/local/lib/python2.7/site-packages/django/core/management/__init__.py", line 120, in call_command
          return command.execute(*args, **defaults)
        File "/edx/app/edxapp/venvs/edxapp/local/lib/python2.7/site-packages/django/core/management/base.py", line 445, in execute
          output = self.handle(*args, **options)
        File "/edx/app/edxapp/edx-platform/common/djangoapps/student/management/commands/change_due.py", line 56, in handle
          changer.change_due()
        File "/edx/app/edxapp/edx-platform/common/djangoapps/student/management/commands/change_due.py", line 184, in change_due
          for num, xblock in enumerate(self.xblock_group):
        File "/edx/app/edxapp/edx-platform/common/djangoapps/student/management/commands/change_due.py", line 219, in xblock_group
          usage_key = UsageKey.from_string(self.where)
        File "/edx/app/edxapp/venvs/edxapp/local/lib/python2.7/site-packages/opaque_keys/__init__.py", line 185, in from_string
          namespace, rest = cls._separate_namespace(serialized)
        File "/edx/app/edxapp/venvs/edxapp/local/lib/python2.7/site-packages/opaque_keys/__init__.py", line 205, in _separate_namespace
          namespace, __, rest = serialized.partition(cls.NAMESPACE_SEPARATOR)
          AttributeError: 'BlockUsageLocator' object has no attribute 'partition'
        """
        print("trying to take block by usage_key")
        new_selected_block = key_cycle(selected_block)
        print(new_selected_block.display_name, new_selected_block.location)
        print('_______________________________')
        print(new_selected_block)

        call_command(
            'change_due',
            user=selected_user.username,
            block_key=selected_block.location,
            set_date=set_date
        )
        after = self.write_down_can_answer_results(blocks=self.problems, users=users)

        print(before)
        print()
        print(after)

        for u in users:
            for p in problems:
                ku = u.username
                kl = p.location
                if ku == selected_user.username and kl == selected_block.location:
                    self.assertTrue(not before[kl][ku] and after[kl][ku],
                                    msg="{},{}:".format(ku, kl) + "{};{}".format(before[kl][ku], after[kl][ku]))
                self.assertTrue(before[kl][ku] == after[kl][ku])

    def set_task(self, n_task, type_task=None, category_task='vertical', parent_location=None,
                 due=None):
        items = []
        if due is True:
            due = self.store.get_item(parent_location).get_parent().due
            if not due:
                due = self.days_ago()

        kwargs = {"parent_location": parent_location or self.sequential.location,
                  "category": category_task,
                  "modulestore": self.store,
                  "due": due
                  }
        if type_task:
            kwargs["format"] = type_task

        for _i in range(n_task):
            i = ItemFactory.create(**kwargs)
            items.append(i)
        return items

    @staticmethod
    def days_ago(days=10):
        return datetime.now() - timedelta(days=days)

    @staticmethod
    def block_user_date(block, user):
        override = get_override_for_user(user, block, "due")
        due = override or block.due
        if not due:
            return None
        due = due.replace(tzinfo=None)
        return due

    def block_user_can_answers(self, block, user):
        due = self.block_user_date(block, user)
        if not due:
            return None
        return self.now < due

    def write_down_can_answer_results(self, blocks, users):
        log = dict()
        for b in blocks:
            block_dict = dict()
            for u in users:
                block_dict[u.username] = self.block_user_date(b, u)
            log[b.location] = block_dict
        return log

# python manage.py lms test student.management.tests.test_change_due --settings=test
