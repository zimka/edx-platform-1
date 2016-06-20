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
from urllib2 import urlopen
from xml.dom.minidom import parseString
from collections import Counter, namedtuple
from datetime import datetime, timedelta
from openedx.core.djangoapps.course_groups.partition_scheme import get_cohorted_user_partition
import urllib
import json
import re
from openedx.core.djangoapps.course_groups.cohorts import get_course_cohort_settings, get_course_cohorts


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

@login_required
def course_validator(request, course_key_string=None):
    return course_validator_handler(request, course_key_string)


def course_validator_handler(request, course_key_string=None):
    CV = CourseValid(request, course_key_string)
    CV.validate()
    return CV.report()

def _youtube_duration(video_id):
    if not video_id:
        return None
    api_key = 'AIzaSyCnxGGegKJ1_R-cEVseGUrAcFff5VHXgZ0'
    searchUrl = "https://www.googleapis.com/youtube/v3/videos?id=" + video_id + "&key=" + api_key + "&part=contentDetails"
    response = urllib.urlopen(searchUrl).read()
    data = json.loads(response)
    if data.get('error', False):
        return u"Error while video duration check:{}".format(data['error'])
    all_data = data['items']
    if len(all_data):
        contentDetails = all_data[0]['contentDetails']
        duration = contentDetails['duration']
        temp = re.split(r'(\d+)', duration)
        times = filter(lambda x: x.isdigit(), temp)
        if len(times) > 3:
            return u"Is this video longer than one 24 hours?"
        return unicode(sum([int(x)*60**num for num, x in enumerate(reversed(times))]))
    else:
        return u"Can't find video with such id on youtube."

def _edx_id_duration(edx_video_id):
    if not edx_video_id:
        return None
    try:
        from openedx.core.djangoapps.video_evms.api import get_video_info
    except ImportError:
        return "Can't check edx video id"
    temp = get_video_info(edx_video_id).get('duration', "Error: didn't get duration from server")
    num = round(float(temp))
    return unicode(num)


class CourseValid():
    """Contains course validation scenarios and formates validation report"""
    def __init__(self, request, course_key_string):
        self.request = request
        self.course_key = CourseKey.from_string(course_key_string)
        self.items = modulestore().get_items(self.course_key)
        self.results = {}
        self.root, self.edges = self.build_items_tree()

    def validate(self):
        self.val_video()
        self.val_grade()
        self.val_group()
        self.val_xmodule()
        self.val_dates()
        self.val_cohorts()

    def val_video(self):
        items = self.items

        video_items = [i for i in items if i.category=="video"]

        video_strs = []
        for v in video_items:
            mes = ""
            if v.youtube_id_1_0:
                mes += _youtube_duration(v.youtube_id_1_0) +' '
            if v.edx_video_id:
                mes += _edx_id_duration(v.edx_video_id)
            video_strs.append(u"{} - {}".format(v.display_name, mes))
        report = []
        for v in video_items:
            if not (v.youtube_id_1_0) and not (v.edx_video_id):
                report.append("Looks like video '{}' in '{}' "
                              "is broken".format(v.display_name, v.get_parent().display_name))

        results = {"head": "video_id - video_duration",
                   "body":video_strs,
                   "report":report,
                   }
        self.results["video"] = results


    def val_grade(self):
        report = []
        course_details = CourseGradingModel.fetch(self.course_key)
        graders = course_details.graders
        grade_strs = []
        grade_attributes = ["type", "min_count", "drop_count", "weight"]
        grade_types = []
        grade_nums = []
        grade_weights = []

        for g in graders:
            grade_strs.append(u" - ".join(unicode(g[k]) for k in grade_attributes))
            grade_types.append(unicode(g["type"]))
            grade_nums.append(unicode(g["min_count"]))
            try:
                grade_weights.append(float(g["weight"]))
            except ValueError:
                report.append("Error during weight summation")

        head = "grade_name - grade_count - grade_kicked - grade_weight"

        if sum(grade_weights) != 100:
           report.append(u"Tasks weight sum({}) is not equal to 100".format(sum(grade_weights)))
        grade_items = [i for i in self.items if i.format is not None]
        for num, key in enumerate(grade_types):
            cur_items = [i for i in grade_items if unicode(i.format)==key]

            if len(cur_items) != grade_nums[num]:
                r = u"Task type '{}': supposed to be {} " \
                    u", found in course {}".format(key, grade_nums[num], len(cur_items))
                report.append(r)

        results = {
            "head": head,
            "body": grade_strs,
            "report": report,
        }

        self.results["grade"] = results

    def val_group(self):
        store = modulestore()
        with store.bulk_operations(self.course_key):
            course = modulestore().get_course(self.course_key)
            content_group_configuration = GroupConfiguration.get_or_create_content_group(store, course)
        groups = content_group_configuration["groups"]
        is_g_used = lambda x: bool(len(x["usage"]))
        group_strs = [u"{} - {}".format(g["name"], is_g_used(g)) for g in groups]
        head = "group_name - group_used"
        report = []
        results = {
            "head":head,
            "body":group_strs,
            "report":report,
        }
        self.results["group"] = results

    def val_xmodule(self):
        xmodule_counts = Counter([i.category for i in self.items])
        categories = ["course",
                      "chapter",
                      "sequential",
                      "vertical",
                      ]
        categorized_dict = {c: xmodule_counts[c] for c in categories}
        ordered_categorized_pairs = [(k, categorized_dict[k]) for k in categories]
        xmodule_strs = ["{} - {}".format(k, v) for k, v in ordered_categorized_pairs]
        uncat_keys = set(xmodule_counts.keys()) - set(categories)
        uncategorized_dict = {c: xmodule_counts[c] for c in uncat_keys}
        others_sum = sum(uncategorized_dict.values())
        xmodule_strs.append("others - {}".format(others_sum))
        head = 'xmodule_type - xmodule_count'
        report = []
        categorized_items = [i for i in self.items if i.category in categories]
        for i in categorized_items:
            if not len(i.get_children()):
                s = "Block '{}' doesn't have any inner blocks or tasks".format(i.display_name)
                report.append(s)
        results = {
            "head": head,
            "body": xmodule_strs,
            "report": report
        }
        self.results['module'] = results

    def val_dates(self):
        report = []
        items = self.items

        def check_dates(item_num):
            cur = items[item_num]
            cur_edges = [e for e in self.edges if e[0]==item_num]
            for _, next_num in cur_edges:
                next = items[next_num]
                if next.start < cur.start:
                    s= u"'{}' block has start date {}, but his parent '{}' " \
                       u"has later start date {}".format(next.display_name, next.start,
                                                  cur.display_name,  cur.start)
                    report.append(s)
                check_dates(next_num)
        check_dates(self.root)
        now = datetime.now(items[0].start.tzinfo)

        if all([x.start>now for x in items]):
            report.append("All course release dates are later than {}".format(now))
        elif all([x.visible_to_staff_only for x in items if x.start<now and x.category!='course']):
            report.append("All released stuff is invisible for students")
        result = {
            "head":"dates",
            "body": "",
            "report": report
        }
        self.results["dates"] = result

    def val_cohorts(self):
        course = modulestore().get_course(self.course_key)
        content_group_configuration = get_cohorted_user_partition(course)
        item = [i for i in self.items if i.display_name=='Final'][0]

        #_print_all(course = modulestore().get_course(self.course_key))#get_course_cohort_settings(self.course_key))
        course = modulestore().get_course(self.course_key)
        cohs = get_course_cohorts(course)
        names = [getattr(x,'name',"NONAME") for x in cohs]
        users = [getattr(x, 'users', "NONAME").all() for x in cohs]
        report = []
        cohort_strs = []
        for num, x in enumerate(names):
            print(x,  len(users[num]))
            cohort_strs.append("{} - {}".format(x, len(users[num])))
        result = {
            "head": "cohorts",
            "body": cohort_strs,
            "report": report
        }
        self.results["cohorts"] = result

    def build_items_tree(self):
        items = self.items
        course_root = None
        for num, i in enumerate(items):
            if i.category=='course':
                course_root = num
        if course_root is None:
            raise ValueError("No course in {} ".format([i.category for i in items]))
        edges = []
        ids = [i.url_name for i in items]

        def deep_search(item_num):
            item = items[item_num]
            children_ids = [x.url_name for x in item.get_children()]
            children_nums = [num for num, x in enumerate(ids) if x in children_ids]
            for c in children_nums:
                edges.append([item_num, c])
                deep_search(c)

        deep_search(course_root)
        return course_root, edges
        """
        root = items[course_root]

        print(root.get_parent())

        vertices = set()
        for x,y in edges:
            vertices.add(x)
            vertices.add(y)
        not_vert = [i for i in range(len(ids)) if i not in vertices]
        print(not_vert)
        for i in range(len(ids)):
            par = items[i].get_parent()
            if par is not None:
                print(i, par.url_name in ids)
            else:
                print(i, 'None')
        """

    def report(self):
        r = HttpResponse()
        s = ''
        sln = "&#13"
        for key in self.results:
            curr = self.results[key]
            s += curr["head"] + sln
            s += sln.join(curr["body"])
            s += sln
            if len(curr['report']):
                s += sln.join(curr["report"])
            else:
                s += 'OK'
            s+= sln
            s += sln
        r.write("<textarea cols='60' rows='60'>")
        r.write(s)
        r.write("</textarea>")
        self.build_items_tree()
        return r

class CourseValidator(XBlock):
    pass