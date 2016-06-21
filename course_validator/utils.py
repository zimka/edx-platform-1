# -*- coding: utf-8 -*-
import json
import re
import urllib
from collections import namedtuple


Report = namedtuple("Report", ["name", "head", "body", "warnings"])


def _build_items_tree(items):
    """Построение дерева курса с корнем в итеме с category='course'"""
    course_root = None
    for num, i in enumerate(items):
        if i.category=="course":
            course_root = num
    if course_root is None:
        raise ValueError("No course in {}".format([i.category for i in items]))
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


def _youtube_duration(video_id):
    """
    Определяет длительность видео с YouTube по video_id, гда
    video_id это часть url: https://youtu.be/$video_id$"""
    if not video_id:
        return None
    api_key = "AIzaSyCnxGGegKJ1_R-cEVseGUrAcFff5VHXgZ0"
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
    """Определяет длительность видео по предоставленному edx_video_id"""
    if not edx_video_id:
        return None
    try:
        from openedx.core.djangoapps.video_evms.api import get_video_info
    except ImportError:
        return u"Can't check edx video id: no api"
    temp = get_video_info(edx_video_id).get('duration', "Error: didn't get duration from server")
    num = round(float(temp))
    return unicode(num)