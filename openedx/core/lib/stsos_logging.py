import logging


class StsosFilter(logging.Filter):
    def filter(self, record):
        if 'lms.djangoapps.grades.signals.stsos' in  record.name:
            return True
