"""
Tests for npoed session monitoring
"""
import ddt
from django.test import TestCase
from mock import patch, call
from .utils import ExamSessionSet, SessionEntry


@ddt.ddt
class TestNpoedSessionMonitoring(TestCase):
    @ddt.data(
        (SessionEntry(ip="128.0.0.1", key="sessionkey"), SessionEntry(ip="192.168.0.1", key="abracadabra")),
        (SessionEntry(ip="0.0.0.0", key="sessionkey"), SessionEntry(ip="0.0.0.0", key="abracadabra")),
        (SessionEntry(ip="0.0.0.0", key="abracadabra"), SessionEntry(ip="0.0.0.0", key="abracadabra")),
    )
    @ddt.unpack
    def test_exam_session_set_summation(self, entry1, entry2):
        """
        Check that summation is set-like
        """
        first_set = ExamSessionSet()
        first_set.add(entry1)
        first_set.add(entry2)

        second_set = ExamSessionSet()

        sum_set = first_set + second_set
        self.assertEqual(sum_set, first_set, "First:{}, Sum:{}".format(str(first_set), str(sum_set)))

        second_set.add(entry1)
        sum_set = first_set + second_set
        self.assertTrue(sum_set==first_set, "First:{}, Sum:{}".format(str(first_set), str(sum_set)))

        first_set = ExamSessionSet()
        first_set.add(entry1)

        sum_set2 = first_set + second_set
        self.assertTrue(sum_set==first_set, "Sum:{}, Sum2:{}".format(str(sum_set), str(sum_set2)))
