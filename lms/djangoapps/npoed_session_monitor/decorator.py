from .models import ExamSessionSetStorage, ExamSessionSet
from .utils import get_session_entry


def npoed_session_monitoring(func):
    """
    At the end of exam we push suspicious attempts from cache to db.
    This decorator should be applied to get method of edx_proctoring.views.StudentProctoredExamAttemptCollection.
    """
    def get(self, request):
        response = func(self, request)
        data = response.data
        if not data.get('in_timed_exam', False):
            return response
        session_entry = get_session_entry(request)
        attempt_pk = data['attempt_id']
        exam_session_set = ExamSessionSetStorage.get(attempt_pk)
        if not exam_session_set:
            exam_session_set = ExamSessionSet()

        if session_entry not in exam_session_set:
            exam_session_set.add(session_entry)
            ExamSessionSetStorage.set(attempt_pk, exam_session_set)
        return response
    return get
