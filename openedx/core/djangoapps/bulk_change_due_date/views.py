import logging
import json
from collections import OrderedDict
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST, require_GET
from django.db import transaction
from django.utils.translation import ugettext as _
from util.json_request import JsonResponse, JsonResponseBadRequest
from opaque_keys.edx.keys import CourseKey
from .utils import are_change_due_keys_broken
from .utils import ACTION_KEYS_BY_TYPE
from .tasks import submit_change_due_task

log = logging.getLogger(__name__)


@transaction.non_atomic_requests
@require_POST
@ensure_csrf_cookie
def post_change_due(request, course_id):
    """ Changes due dates for given cohort/user for given block/course"""
    data = request.POST
    params = OrderedDict()
    if 'user' in data['who']:
        if not data['user-name']:
            return JsonResponse({"message": _("User is not specified")}, status=400)
        params['user'] = data['user-name']
    if 'cohort' in data['who']:
        try:
            params['cohort'] = data['cohort']
        except:
            return JsonResponse({"message": _("Cohort is not specified")}, status=400)
    if 'course' in data['where']:
        params['course_key'] = course_id
    if 'block' in data['where']:
        if not data['location']:
            return JsonResponse({"message": _("Location is not specified")}, status=400)
        params['block_key'] = data['location']

    if 'add' in data['when']:
        if not data['add-days']:
            return JsonResponse({"message": _("Days to add are not specified")}, status=400)
        params['add_days'] = data['add-days']
    if 'set' in data['when']:
        if not data['set-date']:
            return JsonResponse({"message": _("Date is not specified")}, status=400)
        params['set_date'] = data['set-date']
    course_key = CourseKey.from_string(course_id)
    failed_check = are_change_due_keys_broken(params, course_key)
    if failed_check:
        return JsonResponse({"message": failed_check}, status=400)

    submit_change_due_task(request, course_key, params)
    return JsonResponse(status=200)

@require_GET
def get_tasks(request, course_id):
    # usually lms.* uses openedx.*
    from lms.djangoapps.instructor_task.models import InstructorTask
    task_type = 'change_due_dates'
    course_key = CourseKey.from_string(course_id)
    tasks = InstructorTask.objects.filter(task_type=task_type, course_id=course_key).order_by('-updated')
    task_dicts = []
    for t in tasks:
        current = {
            "id": t.task_id,
            "author": t.requester.username,
            "status": t.task_output.strip('"') if t.task_state == "SUCCESS" else t.task_state.lower(),
            "date": str(t.updated.replace(microsecond=0, tzinfo=None))
        }
        task_input = json.loads(t.task_input)
        task_args = {"who": None, "when": None, "where": None}
        try:
            pairs = dict((key, task_input["values"][num]) for num, key in enumerate(task_input["keys"]))
            for wh_ in ACTION_KEYS_BY_TYPE:
                for type_ in ACTION_KEYS_BY_TYPE[wh_]:
                    if type_ in pairs:
                        task_args[wh_] = pairs[type_]
        except Exception as e:
            logging.error(u"Exception during instructor 'change_due' task processing: '{}'".format(unicode(e)))
        current.update(task_args)
        task_dicts.append(current)
    return JsonResponse({"tasks": task_dicts})
