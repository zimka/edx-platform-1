from student.auth import has_course_author_access, has_studio_write_access, has_studio_read_access
from django.contrib.auth.decorators import login_required
from util.json_request import JsonResponse, JsonResponseBadRequest, expect_json
from xmodule.modulestore.django import modulestore

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, Http404
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.core.urlresolvers import reverse
from xblock.core import XBlock
from xblock.fields import Scope, Integer, String
from models.settings.course_grading import CourseGradingModel

from contentstore.course_group_config import GroupConfiguration
from datetime import timedelta
from urllib2 import urlopen
from xml.dom.minidom import parseString
from collections import Counter


def _print_all(item):
    ats = dir(item)
    for at in ats:
        try:
            t = getattr(item, at)
            if callable(t):
                print(at, "callable")
            else:
                print(at, t)
        except Exception as e:
            print(at, e.message)



def get_course_and_check_access(course_key, user, depth=0):
    """
    Internal method used to calculate and return the locator and course module
    for the view functions in this file.
    """
    if not has_studio_read_access(user, course_key):
        raise PermissionDenied()
    course_module = modulestore().get_course(course_key, depth=depth)

    return course_module

def get_youtube_time(vid):
    url = 'https://gdata.youtube.com/feeds/api/videos/{0}?v=2'.format(vid)
    print(url)
    s = urlopen(url).read()
    d = parseString(s)
    e = d.getElementsByTagName('yt:duration')[0]
    a = e.attributes['seconds']
    v = int(a.value)
    #t = timedelta(seconds=v)
    return v

@login_required
def course_validator(request, course_key_string=None):
    """
    Checks consistency of courses according to the scenario rules
    """
    try:
        course_key = CourseKey.from_string(course_key_string)
        items = modulestore().get_items(course_key)

        video_items = [i for i in items if i.category=="video"]
        video_strs = [u"{} - {}".format(i.display_name, i.youtube_id_1_0) for i in video_items]

        course_details = CourseGradingModel.fetch(course_key)
        graders = course_details.graders
        grade_strs = []
        grade_keys = ["type", "min_count", "drop_count", "weight"]
        for g in graders:
            grade_strs.append(u" - ".join(unicode(g[k]) for k in grade_keys))

        store = modulestore()
        with store.bulk_operations(course_key):
            course = get_course_and_check_access(course_key, request.user)
            content_group_configuration = GroupConfiguration.get_or_create_content_group(store, course)
        groups = content_group_configuration['groups']
        is_g_used = lambda x: bool(len(x['usage']))
        group_strs = [u"{} - {}".format(g["name"], is_g_used(g)) for g in groups]

        xmodule_counts = Counter([i.category for i in items])
        categories = ["course",
                "chapter",
                "sequential",
                "vertical",
                ]
        categorized_dict = {c: xmodule_counts[c] for c in categories}
        ordered_categorized_pairs = [(k, categorized_dict[k]) for k in categories]
        xmodule_strs = ["{} - {}".format(k,v) for k,v in ordered_categorized_pairs]
        uncat_keys = set(xmodule_counts.keys()) - set(categories)
        uncategorized_dict = {c: xmodule_counts[c] for c in uncat_keys}
        others_sum = sum(uncategorized_dict.values())
        xmodule_strs.append("others - {}".format(others_sum))

    except:
        print("exception!")
        return redirect(reverse("home"))

    _print_all(video_items[0])

    output = []
    subsections = ['video_id - video_duration',
                   'grade_name - grade_count - grade_kicked - grade_weight',
                   'group_name - group_used',
                   'xmodule_type - xmodule_count',
                    ]
    strings = [video_strs,
               grade_strs,
               group_strs,
               xmodule_strs,
               ]
    for sect, strs in zip(subsections, strings):
        output.append(sect)
        output.extend(strs)
        output.append(" ")
    response = HttpResponse()
    for s in output:
        response.write('<p>'+s+'</p>')
    return response


class CourseValidator(XBlock):
    pass


