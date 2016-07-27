"""
The file contains utils
"""
from django.conf import settings
from django.core.cache import cache

from courseware.transformers.grades import GradesTransformer
from openedx.core.lib.cache_utils import memoized
from openedx.core.djangoapps.content.block_structure.api import get_course_in_cache
from xblock.core import XBlock


class MaxScoresCache(object):
    """
    A cache for unweighted max scores for problems.

    The key assumption here is that any problem that has not yet recorded a
    score for a user is worth the same number of points. An XBlock is free to
    score one student at 2/5 and another at 1/3. But a problem that has never
    issued a score -- say a problem two students have only seen mentioned in
    their progress pages and never interacted with -- should be worth the same
    number of points for everyone.
    """
    def __init__(self, cache_prefix):
        self.cache_prefix = cache_prefix
        self._max_scores_cache = {}
        self._max_scores_updates = {}

    @classmethod
    def create_for_course(cls, course):
        """
        Given a CourseDescriptor, return a correctly configured `MaxScoresCache`

        This method will base the `MaxScoresCache` cache prefix value on the
        last time something was published to the live version of the course.
        This is so that we don't have to worry about stale cached values for
        max scores -- any time a content change occurs, we change our cache
        keys.
        """
        if course.subtree_edited_on is None:
            # check for subtree_edited_on because old XML courses doesn't have this attribute
            cache_key = u"{}".format(course.id)
        else:
            cache_key = u"{}.{}".format(course.id, course.subtree_edited_on.isoformat())
        return cls(cache_key)

    def fetch_from_remote(self, locations):
        """
        Populate the local cache with values from django's cache
        """
        remote_dict = cache.get_many([self._remote_cache_key(loc) for loc in locations])
        self._max_scores_cache = {
            self._local_cache_key(remote_key): value
            for remote_key, value in remote_dict.items()
            if value is not None
        }

    def push_to_remote(self):
        """
        Update the remote cache
        """
        if self._max_scores_updates:
            cache.set_many(
                {
                    self._remote_cache_key(key): value
                    for key, value in self._max_scores_updates.items()
                },
                60 * 60 * 24  # 1 day
            )

    def _remote_cache_key(self, location):
        """Convert a location to a remote cache key (add our prefixing)."""
        return u"grades.MaxScores.{}___{}".format(self.cache_prefix, unicode(location))

    def _local_cache_key(self, remote_key):
        """Convert a remote cache key to a local cache key (i.e. location str)."""
        return remote_key.split(u"___", 1)[1]

    def num_cached_from_remote(self):
        """How many items did we pull down from the remote cache?"""
        return len(self._max_scores_cache)

    def num_cached_updates(self):
        """How many local updates are we waiting to push to the remote cache?"""
        return len(self._max_scores_updates)

    def set(self, location, max_score):
        """
        Adds a max score to the max_score_cache
        """
        loc_str = unicode(location)
        if self._max_scores_cache.get(loc_str) != max_score:
            self._max_scores_updates[loc_str] = max_score

    def get(self, location):
        """
        Retrieve a max score from the cache
        """
        loc_str = unicode(location)
        max_score = self._max_scores_updates.get(loc_str)
        if max_score is None:
            max_score = self._max_scores_cache.get(loc_str)

        return max_score


class ProgressSummary(object):
    """
    Wrapper class for the computation of a user's scores across a course.

    Attributes
       chapters: a summary of all sections with problems in the course. It is
       organized as an array of chapters, each containing an array of sections,
       each containing an array of scores. This contains information for graded
       and ungraded problems, and is good for displaying a course summary with
       due dates, etc.

       weighted_scores: a dictionary mapping module locations to weighted Score
       objects.

       locations_to_children: a function mapping locations to their
       direct descendants.
    """
    def __init__(self, chapters, weighted_scores, locations_to_children):
        self.chapters = chapters
        self.weighted_scores = weighted_scores
        self.locations_to_children = locations_to_children

    def score_for_module(self, location):
        """
        Calculate the aggregate weighted score for any location in the course.
        This method returns a tuple containing (earned_score, possible_score).

        If the location is of 'problem' type, this method will return the
        possible and earned scores for that problem. If the location refers to a
        composite module (a vertical or section ) the scores will be the sums of
        all scored problems that are children of the chosen location.
        """
        if location in self.weighted_scores:
            score = self.weighted_scores[location]
            return score.earned, score.possible
        children = self.locations_to_children[location]
        earned = 0.0
        possible = 0.0
        for child in children:
            child_earned, child_possible = self.score_for_module(child)
            earned += child_earned
            possible += child_possible
        return earned, possible


@memoized
def block_types_with_scores():
    """
    Returns the block types that could have a score.

    Something might be a scored item if it is capable of storing a score
    (has_score=True). We also have to include anything that can have children,
    since those children might have scores. We can avoid things like Videos,
    which have state but cannot ever impact someone's grade.
    """
    return frozenset(
        cat for (cat, xblock_class) in XBlock.load_classes() if (
            getattr(xblock_class, 'has_score', False) or getattr(xblock_class, 'has_children', False)
        )
    )


def possibly_scored(usage_key):
    """
    Returns whether the given block could impact grading (i.e. scored, or has children).
    """
    return usage_key.block_type in block_types_with_scores()


def grading_context_for_course(course):
    """
    Same as grading_context, but takes in a course object.
    """
    course_structure = get_course_in_cache(course.id)
    return course.grading.grading_context(course_structure)


def weighted_score(raw_correct, raw_total, weight):
    """Return a tuple that represents the weighted (correct, total) score."""
    # If there is no weighting, or weighting can't be applied, return input.
    if weight is None or raw_total == 0:
        return (raw_correct, raw_total)
    return (float(raw_correct) * weight / raw_total, float(weight))


def get_score(user, block, scores_client, submissions_scores_cache, max_scores_cache):
    """
    Return the score for a user on a problem, as a tuple (correct, total).
    e.g. (5,7) if you got 5 out of 7 points.

    If this problem doesn't have a score, or we couldn't load it, returns (None,
    None).

    user: a Student object
    block: a BlockStructure's BlockData object
    scores_client: an initialized ScoresClient
    submissions_scores_cache: A dict of location names to (earned, possible) point tuples.
           If an entry is found in this cache, it takes precedence.
    max_scores_cache: a MaxScoresCache
    """
    submissions_scores_cache = submissions_scores_cache or {}

    if not user.is_authenticated():
        return (None, None)

    location_url = unicode(block.location)
    if location_url in submissions_scores_cache:
        return submissions_scores_cache[location_url]

    if not getattr(block, 'has_score', False):
        # These are not problems, and do not have a score
        return (None, None)

    # Check the score that comes from the ScoresClient (out of CSM).
    # If an entry exists and has a total associated with it, we trust that
    # value. This is important for cases where a student might have seen an
    # older version of the problem -- they're still graded on what was possible
    # when they tried the problem, not what it's worth now.
    score = scores_client.get(block.location)
    cached_max_score = max_scores_cache.get(block.location)
    if score and score.total is not None:
        # We have a valid score, just use it.
        correct = score.correct if score.correct is not None else 0.0
        total = score.total
    elif cached_max_score is not None and settings.FEATURES.get("ENABLE_MAX_SCORE_CACHE"):
        # We don't have a valid score entry but we know from our cache what the
        # max possible score is, so they've earned 0.0 / cached_max_score
        correct = 0.0
        total = cached_max_score
    else:
        # This means we don't have a valid score entry and we don't have a
        # cached_max_score on hand. We know they've earned 0.0 points on this.
        correct = 0.0
        total = block.transformer_data[GradesTransformer].max_score

        # Problem may be an error module (if something in the problem builder failed)
        # In which case total might be None
        if total is None:
            return (None, None)
        else:
            max_scores_cache.set(block.location, total)

    return weighted_score(correct, total, block.weight)


def grade_for_percentage(grade_cutoffs, percentage):
    """
    Returns a letter grade as defined in grading_policy (e.g. 'A' 'B' 'C' for 6.002x) or None.

    Arguments
    - grade_cutoffs is a dictionary mapping a grade to the lowest
        possible percentage to earn that grade.
    - percentage is the final percent across all problems in a course
    """

    letter_grade = None

    # Possible grades, sorted in descending order of score
    descending_grades = sorted(grade_cutoffs, key=lambda x: grade_cutoffs[x], reverse=True)
    for possible_grade in descending_grades:
        if percentage >= grade_cutoffs[possible_grade]:
            letter_grade = possible_grade
            break

    return letter_grade
