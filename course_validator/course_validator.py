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

from datetime import timedelta
from urllib2 import urlopen
from xml.dom.minidom import parseString

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
    Checks consitency of courses according to the scenario rules
    """
    try:
        usr = request.user
        ck = CourseKey.from_string(course_key_string)
        """
        course_module = get_course_and_check_access(ck, usr)
        sections = course_module.get_children()

        child1 = sections[0]
        print(child1.category)
        child2 = child1.get_children()
        print(child2[0].category)
        """
        items = modulestore().get_items(ck)
        report = []
        video_items = [i for i in items if i.category=="video"]
        vi = video_items[0]
        attrs = dir(vi)
        print(vi.editable_metadata_fields.get("youtube_id_1_0", 'woops'))
        vid = vi.editable_metadata_fields.get("youtube_id_1_0",{'value':'vooops'}).get("value")
        print(vid)
        print(get_youtube_time(vid))
    except:
        print("exception!")

    return redirect(reverse("home"))


class CourseValidator(XBlock):
    pass


