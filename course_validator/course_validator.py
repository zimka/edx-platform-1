# -*- coding: utf-8 -*-
from collections import Counter
from contentstore.course_group_config import GroupConfiguration
from datetime import datetime
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.core.urlresolvers import reverse
import json
import logging
from models.settings.course_grading import CourseGradingModel
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.course_groups.cohorts import get_course_cohorts, get_course_cohort_settings
from xmodule.modulestore.django import modulestore
from xblock.core import XBlock
from .utils import Report, youtube_duration, edx_id_duration, _print_all, _build_items_tree
from edxmako.shortcuts import render_to_response
import time
from datetime import timedelta

@login_required
def course_validator_handler(request, course_key_string=None):
    """Обработчик url на проверку курса"""
    if request.method != 'GET':
        return redirect(reverse('course_handler', course_key_string))
    CV = CourseValid(request, course_key_string)
    CV.validate()
    CV.send_log()
    course_key = CourseKey.from_string(course_key_string)
    course_module = modulestore().get_course(course_key)

    return render_to_response("dev_course_validator.html", {

            "sections":CV.get_sections_for_rendering(),
            "context_course":course_module
            })


class CourseValid():
    """Проверка сценариев и формирование логов"""

    def __init__(self, request, course_key_string):
        self.request = request
        self.course_key = CourseKey.from_string(course_key_string)
        self.items = modulestore().get_items(self.course_key)
        self.root, self.edges = _build_items_tree(self.items)
        self.reports = []

    def validate(self):
        """Запуск всех сценариев проверок"""
        scenarios = [
            "video", "grade", "group", "xmodule",
            "dates", "cohorts", "proctoring",
            "group_visibility",
        ]
        results = []
        for sc in scenarios:
            val_name = "val_{}".format(sc)
            validation = getattr(self, val_name)
            report = validation()
            if report is not None:
                results.append(report)
        self.reports = results

    def get_sections_for_rendering(self):
        sections = []
        for r in self.reports:
            sec = {"name":r.name, "passed":not bool(len(r.warnings))}
            if len(r.body):
                sec["output"] = True
                sec["head"] = r.head.split(' - ')
                sec["body"] = [s.split(' - ') for s in r.body]
            else:
                sec["output"] = False

            if not len(r.warnings):
                sec["warnings"] = [u"OK"]
            else:
                sec["warnings"] = r.warnings
            sections.append(sec)
        return sections

    def get_HTML_report(self):
        """Формирование отчета из результатов проверок"""
        response = HttpResponse()
        message = ""
        delim = "\n"
        for curr in self.reports:
            message += curr.name + delim
            if len(curr.body):
                message += curr.head + delim
                message += delim.join(curr.body) + delim
            if len(curr.warnings):
                message += delim.join(curr.warnings) + delim
            message += delim

        response.write("<textarea cols='60' rows='60'>")
        response.write(message)
        response.write("</textarea>")
        return response

    def send_log(self):
        """
        Посылает в лог информацию о проверки в виде JSON:
        username, user_email: Данные проверяющего
        datetime: Дата и время
        passed: Пройдены ли без предупреждений проверки:
        warnings: словарь предупреждений (название проверки-предупреждения)
        """
        user = self.request.user
        log = {"username": user.username, "user_email": user.email, "datetime": str(datetime.now())}
        results = []
        passed = True
        for r in self.reports:
            t = u";".join(r.warnings)
            if not len(t):
                t = u'OK'
            else:
                passed = False
            results.append({r.name:t})
        log["warnings"] = results
        log["passed"] = passed
        mes = json.dumps(log)
        if passed:
            logging.info(mes)
        else:
            logging.warning(mes)

    def val_video(self):
        """
        Проверка видео: наличие ссылки на YouTube либо edx_video_id.
        При наличии выводится длительнось видео, при отсутствии в отчет пишется
        предупреждение
        """
        items = self.items
        video_items = [i for i in items if i.category=="video"]

        video_strs = []
        for v in video_items:
            mes = ""
            if v.youtube_id_1_0:
                mes += youtube_duration(v.youtube_id_1_0)
            if v.edx_video_id:
                mes += edx_id_duration(v.edx_video_id)
            video_strs.append(u"{} - {}".format(v.display_name, mes))
        report = []
        for v in video_items:
            if not (v.youtube_id_1_0) and not (v.edx_video_id):
                report.append("No source for video '{}' "
                              "in '{}' ".format(v.display_name, v.get_parent().display_name))
        #Суммирование длительностей всех видео
        total = timedelta()
        # Если нет соединения с видеосервером - писать репорт
        for vstr in video_strs:
            vtime = vstr.split(' - ')[-1]
            if (not (':' in vtime)) and vtime:
                report.append("Can't get response from video {}".format(vstr.split(' - ')[0]))
                continue
            if not vtime:
                continue
            if len(vtime.split(':'))>2:
                t = time.strptime(vtime,"%H:%M:%S")
            else:
                t = time.strptime(vtime,"%M:%S")
            total += timedelta(hours=t.tm_hour, minutes=t.tm_min, seconds=t.tm_sec)

        head = "video_id - video_duration(sum: {})".format(str(total))
        results = Report(name="Video",
            head=head,
            body=video_strs,
            warnings=report,
        )
        return results

    def val_grade(self):
        """
        Проверка оценок:
        1)совпадение указанного и имеющегося количества заданий в каждой проверяемой категории,
        2)проверка равенства 100 суммы весов категории 
        """
        report = []
        course_details = CourseGradingModel.fetch(self.course_key)
        graders = course_details.graders
        grade_strs = []
        grade_attributes = ["type", "min_count", "drop_count", "weight"]
        grade_types = []
        grade_nums = []
        grade_weights = []
        
        #Вытаскиваем типы и количество заданий, прописанных в настройках
        for g in graders:
            grade_strs.append(u" - ".join(unicode(g[attr]) for attr in grade_attributes))
            grade_types.append(unicode(g["type"]))
            grade_nums.append(unicode(g["min_count"]))
            try:
                grade_weights.append(float(g["weight"]))
            except ValueError:
                report.append("Error during weight summation")

        head = "grade_name - grade_count - grade_kicked - grade_weight"
        
        #Проверка суммы весов
        if sum(grade_weights) != 100:
           report.append(u"Tasks weight sum({}) is not equal to 100".format(sum(grade_weights)))
        
        #Проверка совпадения настроек заданий с материалом курса 
        grade_items = [i for i in self.items if i.format is not None]
        for num, key in enumerate(grade_types):
            cur_items = [i for i in grade_items if unicode(i.format)==key]
            if len(cur_items) != int(grade_nums[num]):
                r = u"Task type '{}': supposed to be {} " \
                    u", found in course {}".format(key, grade_nums[num], len(cur_items))
                report.append(r)

        results = Report(name="Grade",
            head= head,
            body= grade_strs,
            warnings=report,
        )
        return results

    def val_group(self):
        """Проверка наличия и использования в курсе групп"""
        store = modulestore()
        with store.bulk_operations(self.course_key):
            course = modulestore().get_course(self.course_key)
            content_group_configuration = GroupConfiguration.get_or_create_content_group(store, course)
        groups = content_group_configuration["groups"]
        
        is_g_used = lambda x: bool(len(x["usage"]))
        #запись для каждой группы ее использования
        group_strs = [u"{} - {}".format(g["name"], is_g_used(g)) for g in groups]
        head = "group_name - group_used"
        report = []

        results = Report(name="Group",
            head=head,
            body=group_strs,
            warnings=report,
        )
        return results

    def val_xmodule(self):
        """Проверка отсутствия пустых блоков, подсчет количества каждой категории блоков"""
        xmodule_counts = Counter([i.category for i in self.items])
        """
        Все категории разделены на первичные(ниже) и
        вторичные - problems, video, polls итд - записывается в others
        Элементы каждой первичной категории подсчитывается и выводятся.
        Для вторичных категорий выводится только сумма элементов всех
        вторичных категорий
        """
        primary_cat = ["course",
                       "chapter",
                       "sequential",
                       "vertical",
                       "problem",
                       "video",
                      ]
        """
        Для exclude_cat НЕ делается проверка вложенных блоков, но
        делается подсчет элементов
        """
        exclude_cat = ["problem",
                       "video",
                       ]
        secondary_cat = set(xmodule_counts.keys()) - set(primary_cat)

        #Словарь 'любая категория'(включая вторичные): количество элементов
        categorized_dict = {c: xmodule_counts[c] for c in primary_cat}
        #Словарь 'первичная категория': количество элементов
        primary_dict = [(k, categorized_dict[k]) for k in primary_cat]
        #Словарь 'вторичная категория' : количество элементов. Оставлен на будущее
        secondary_dict = {c: xmodule_counts[c] for c in secondary_cat}
        secondary_sum = sum(secondary_dict.values())

        xmodule_strs = ["{} - {}".format(k, v) for k, v in primary_dict]
        xmodule_strs.append("others - {}".format(secondary_sum))
        head = "xmodule_type - xmodule_count"
        report = []
        #Проверка отсутствия пустых элементов в перв кат кроме exclude_cat
        check_empty_cat = [x for x in primary_cat if x not in exclude_cat]
        primary_items = [i for i in self.items if i.category in check_empty_cat]
        for i in primary_items:
            if not len(i.get_children()):
                s = "Block '{}'({}) doesn't have any inner blocks or tasks".format(i.display_name, i.category)
                report.append(s)
        results = Report(name="Module",
            head = head,
            body = xmodule_strs,
            warnings= report
        )
        return results

    def val_dates(self):
        """
        Проверка дат:
        1)Даты старта дочерних блоков больше дат старта блока-родителя
        2)Наличие блоков с датой старта меньше $сегодня$
        3)Наличие среди стартававших блоков видимых для студентов
        """
        report = []
        items = self.items
        #Проверка что старт дата child>parent
        for child in items:
            parent = child.get_parent()
            if not parent:
                continue
            if parent.start > child.start:
                mes = u"'{}' block has start date {}, but his parent '{}' " \
                    u"has later start date {}".format(child.display_name, child.start,
                                                      parent.display_name, parent.start)
                report.append(mes)

        #Проверка: Не все итемы имеют дату старта больше сегодня
        now = datetime.now(items[0].start.tzinfo)
        if all([x.start>now for x in items]):
            report.append("All course release dates are later than {}".format(now))
        #Проверка: существуют элементы с датой меньше сегодня, видимые для студентов и
        # это не элемент course
        elif all([x.visible_to_staff_only for x in items if (x.start<now and x.category!="course")]):
            report.append("All released stuff is invisible for students")
        result = Report(name="Dates",
            head=[],
            body=[],
            warnings =report,
        )
        return result

    def val_cohorts(self):
        """Проверка наличия в курсе когорт, для каждой вывод их численности либо сообщение об их отсутствии"""
        course = modulestore().get_course(self.course_key)
        cohorts = get_course_cohorts(course)
        names = [getattr(x,"name") for x in cohorts]
        users = [getattr(x, "users").all() for x in cohorts]
        report = []
        cohort_strs = []
        for num, x in enumerate(names):
            cohort_strs.append("{} - {}".format(x, len(users[num])))
        is_cohorted = get_course_cohort_settings(self.course_key).is_cohorted
        if not is_cohorted:
            cohort_strs=[]
            report.append(u"Cohorts are disabled")
        result = Report(name="Cohorts",
            head="Cohorts - population",
            body= cohort_strs,
            warnings = report,
        )
        return result

    def val_proctoring(self):
        """Проверка наличия proctored экзаменов"""
        course = modulestore().get_course(self.course_key)
        proctor_strs = [
            u"available_proctoring_services - {}".format(getattr(course, "available_proctoring_services", "No such attribute")),
            u"proctoring_service - {}".format(getattr(course, "proctoring_service", "No such attribute"))
            ]

        result = Report(name="Proctoring",
            head = "Parameter - name",
            body = proctor_strs,
            warnings =  [],
        )
        return result

    def val_group_visibility(self):
        """Составление таблицы видимости элементов для групп"""
        store = modulestore()
        with store.bulk_operations(self.course_key):
            course = modulestore().get_course(self.course_key)
            content_group_configuration = GroupConfiguration.get_or_create_content_group(store, course)
        groups = content_group_configuration["groups"]
        group_names = [g["name"]for g in groups]
        name = "Items visibility by group"
        head = "item type - student - " + " - ".join(group_names)
        checked_cats = ["chapter",
                       "sequential",
                       "vertical",
                       "problem",
                       "video",
                        ]

        get_items_by_type = lambda x: [y for y in self.items if y.category == x]

        #Словарь (категория - итемы)
        cat_items = dict([(t, get_items_by_type(t)) for t in checked_cats])

        # Словарь id группы - название группы
        group_id_dict = dict([(g['id'],g['name']) for g in groups])

        conf_id = content_group_configuration['id']
        gv_strs = []
        for cat in checked_cats:
            items = cat_items[cat]
            vis = dict((g,0) for g in group_names)
            vis["student"] = 0
            for it in items:
                if conf_id not in it.group_access:
                    for key in group_names:
                        vis[key] += 1
                else:
                    ids = it.group_access[conf_id]
                    vis_gn_for_itme = [group_id_dict[i] for i in ids]
                    for gn in vis_gn_for_itme:
                        vis[gn] += 1
                if not it.visible_to_staff_only:
                    vis["student"] += 1

            item_category = "{}({})".format(cat, len(items))
            stud_vis_for_cat = str(vis["student"])

            cat_list = [item_category] + [stud_vis_for_cat] + [str(vis[gn]) for gn in group_names]
            cat_str = " - ".join(cat_list)
            gv_strs.append(cat_str)

        return Report(name=name,
                   head=head,
                   body=gv_strs,
                   warnings=[]
            )

class CourseValidator(XBlock):
    pass