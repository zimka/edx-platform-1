import json
from functools import wraps
from django.conf import settings

from lms.djangoapps.courseware.user_state_client import DjangoXBlockUserStateClient
from .models import InstructorResetStudentAttempts


def npoed_instructor_reset_track(func):
    @wraps(func)
    def wrap(course_id, student, module_state_key, requesting_user, delete_module=False):
        removed_answer = ""
        if delete_module:
            block_keys = [module_state_key]
            usc = DjangoXBlockUserStateClient(student)
            xblock_user_states = list(usc.get_many(student.username, block_keys))
            key = "student_answers"
            if xblock_user_states and key in xblock_user_states[0].state:
                removed_answer = json.dumps(xblock_user_states[0].state[key])

        exc = None
        success = True
        result = None
        try:
            result = func(course_id, student, module_state_key, requesting_user, delete_module=delete_module)
        except Exception as e:
            success = False
            exc = e

        action = "delete" if delete_module else "reset"
        InstructorResetStudentAttempts.create(
            instructor_username=requesting_user.username,
            student_username=student.username,
            block_id=str(module_state_key),
            course_id=course_id,
            action=action,
            removed_answer=removed_answer,
            success=success
        )
        if not success:
            raise exc
        return result

    if settings.FEATURES.get("ENABLE_INSTRUCTOR_RESET_TRACK"):
        return wrap
    else:
        return func
