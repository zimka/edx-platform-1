import mock
import unittest
from django.test.utils import override_settings
from openedx.core.djangoapps.grading_policy import (
    get_grading_type, settings, GradingPolicyError, get_grading_class, use_custom_grading
)
from openedx.core.djangoapps.grading_policy.grading import VerticalGrading

FEATURES_WITH_CUSTOM_GRADING = settings.FEATURES.copy()
FEATURES_WITH_CUSTOM_GRADING['ENABLE_CUSTOM_GRADING'] = True


class CustomGradingTestCase(unittest.TestCase):
    """
    Verify that settings with wrong values will raise exceptions
    and with right values change arguments in grading fuctions
    """

    @override_settings(GRADING_TYPE='wrong_type', FEATURES=FEATURES_WITH_CUSTOM_GRADING)
    def test_raises_exception_in_get_grading_type_method(self):
        """
        Raises GradingPolicyError if in settings grading_type set wrong value
        """
        self.assertRaises(GradingPolicyError, get_grading_type)

    def test_raises_exception_in_get_grading_class_method(self):
        name = 'wrong_name'
        self.assertRaises(GradingPolicyError, get_grading_class, name=name)

    def test_return_vertical_grading_plugin_class_from_get_grading_class_method(self):
        """
        Return correct class from get_grading method
        """
        # init excepted values
        expected_value = VerticalGrading.__class__

        # execution function
        res = get_grading_class('vertical')

        # verify results and excepted values
        self.assertEqual(expected_value, res.__class__)

    @override_settings(GRADING_TYPE='vertical', FEATURES=FEATURES_WITH_CUSTOM_GRADING)
    def test_called_get_grading_class_in_use_custom_grading_method(self):
        """
        Test that decorator works correct with correct values in settings
        """
        with mock.patch('openedx.core.djangoapps.grading_policy.get_grading_class',
                        return_value=VerticalGrading) as mock_func:
            with mock.patch.object(VerticalGrading, 'grading_context', return_value=None):
                use_custom_grading('grading_context')(lambda x: x)()
                mock_func.assert_called_with('vertical')
