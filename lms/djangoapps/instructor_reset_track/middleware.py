from track.middleware import TrackMiddleware
from eventtracking import tracker
import json
import logging
from django.contrib.auth.models import User
from lms.djangoapps.courseware.user_state_client import DjangoXBlockUserStateClient
from opaque_keys.edx.keys import UsageKey
from .models import InstructorResetStudentAttempts


class InstructorResetMiddleware(TrackMiddleware):

    @staticmethod
    def _get_user(username_or_email):
        try:
            if "@" in username_or_email:
                user = User.objects.get(email=username_or_email)
            else:
                user = User.objects.get(username=username_or_email)
        except User.DoesNotExist:
            user = None
        return user

    def get_context(self, request):
        context = tracker.get_tracker().resolve_context()
        context.update({"POST": dict(request.POST)})
        return context

    def process_request(self, request):
        if not "reset" in request.path:
            return
        if not json.loads(request.POST['delete_module']): #'delete_module': ['false']
            return

        context = self.get_context(request)

        username = context['POST']['unique_student_identifier'][0]
        block_id = context['POST']['problem_to_reset'][0]
        block_keys = [UsageKey.from_string(block_id)]

        user = self._get_user(username)
        if not user:
            logging.error("User not found for: {}".format(str(username)))
            return

        usc = DjangoXBlockUserStateClient(user)
        removed_answers_list = list(usc.get_many(username, block_keys))
        if not len(removed_answers_list):
            removed_answer = "No answer"
        else:
            removed_answer = json.dumps(removed_answers_list[0][2]['student_answers'])
        request.removed_answer = removed_answer

    def process_response(self, _request, response):
        if not "reset" in _request.path:
            return response
        context = self.get_context(_request)
        if hasattr(_request, "removed_answer"):
            context["removed_answer"] = _request.removed_answer

        if "reset" in response.content:
            context["success"] = True
        else:
            context["success"] = False
        self.write_down_reset(context)
        return super(InstructorResetMiddleware, self).process_response(_request, response)

    def write_down_reset(self, data):
        instructor_username = data['username']
        course_id = data['course_id']
        event_dict = data['POST']
        action = "delete" if json.loads(event_dict['delete_module'][0]) else "reset"
        student_username = event_dict["unique_student_identifier"][0]
        block_id = event_dict['problem_to_reset'][0]
        success = data["success"]
        removed_answer = ""

        if action=="delete":
            removed_answer = data.get("removed_answer", "Error") #we had to remember answer during process_request
        try:
            InstructorResetStudentAttempts.objects.create(
                instructor_username=instructor_username,
                student_username=student_username,
                block_id=block_id,
                course_id=course_id,
                action=action,
                removed_answer=removed_answer,
                success=success
            )
        except Exception as e:
            logging.error("Error during instructor_reset_track: '{}'".format(str(e)))