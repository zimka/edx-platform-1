""""
This grades a single section with the format 'type' and the name 'name'.
"""
import logging
import random
from xmodule.graders import CourseGrader

log = logging.getLogger("edx.graders")


class SingleSectionGrader(CourseGrader):
    """
    This grades a single section with the format 'type' and the name 'name'.

    If the name is not appropriate for the short short_label or category, they each may
    be specified individually.
    """
    # pylint: disable=redefined-builtin
    def __init__(self, type, name, short_label=None, category=None):
        self.type = type
        self.name = name
        self.short_label = short_label or name
        self.category = category or name

    def grade(self, grade_sheet, generate_random_scores=False):
        found_score = None
        if self.type in grade_sheet:
            for score in grade_sheet[self.type]:
                if score.section == self.name:
                    found_score = score
                    break

        if found_score or generate_random_scores:
            if generate_random_scores:  	# for debugging!
                earned = random.randint(2, 15)
                possible = random.randint(earned, 15)
            else:   # We found the score
                earned = found_score.earned
                possible = found_score.possible

            percent = earned / float(possible)
            detail = u"{name} - {percent:.0%} ({earned:.3n}/{possible:.3n})".format(
                name=self.name,
                percent=percent,
                earned=float(earned),
                possible=float(possible)
            )

        else:
            percent = 0.0
            detail = u"{name} - 0% (?/?)".format(name=self.name)

        breakdown = [{'percent': percent, 'label': self.short_label,
                      'detail': detail, 'category': self.category, 'prominent': True}]

        return {
            'percent': percent,
            'section_breakdown': breakdown,
            #No grade_breakdown here
        }
