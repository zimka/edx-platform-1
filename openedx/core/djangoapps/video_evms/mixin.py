# -*- coding: utf-8 -*-
from xmodule.video_module.video_module import own_metadata
from functools import wraps

try:
    from .api import get_course_edx_val_ids
except:
    get_course_edx_val_ids = lambda x: [{"display_name": u"None", "value": ""}]


class VideoDescriptoEVMSMixin(object):
    """
    This mixin for video_module.VideoDescriptor modifies studio view for video block.
    For correct work you also must wrap VideoDescriptor.editor_saved by EVMS_editor_saved_dec
    Now user can change edx_video_id's according to available id's from EVMS server.
    Mixin is supposed to be the first parent.
    """
    def __init__(self,*args, **kwargs):
        super(VideoDescriptoEVMSMixin, self).__init__(*args, **kwargs)
        if self.edx_video_id != self.edx_dropdown_video_id:
            self.edx_dropdown_video_id = self.edx_video_id

    def studio_view(self, context):
        self.set_video_evms_values()
        return super(VideoDescriptoEVMSMixin, self).studio_view(context)

    @staticmethod
    def edx_dropdown_video_overriden(s):
        return "'Additional value': {}".format(s)

    def synch_edx_id(self, old_metadata=None, new_metadata=None):
        """
        Согласует данные в полях edx_dropdown_video_id и edx_video_id перед сохранением
        :return:
        """
        dropdown_eid = self.edx_dropdown_video_id
        native_eid = self.edx_video_id
        if dropdown_eid == native_eid:
            return

        def master_native(eid):
            block = self.fields["edx_dropdown_video_id"]
            values = [v["value"] for v in block.values]
            if eid not in values:
                block._values.append({"display_name": self.edx_dropdown_video_overriden(eid), "value": eid})
            self.edx_dropdown_video_id = eid

        def master_dropdown(eid):
            if eid:
                self.edx_video_id = eid
            else:
                self.edx_video_id = ""

        """
        Смотрим какое поле поменял пользователь: это поле будет master
        """
        if not old_metadata and not new_metadata:
            """
            метаданные не передали - считаем edx_dropdown_video_id мастером, т.к. уже есть возможность
            сделать edx_video_id мастером явно, поставив в edx_dropdown_video_id: None
            """
            master_dropdown(dropdown_eid)
            return

        old_native_eid = old_metadata.get('edx_video_id', None)
        new_native_eid = new_metadata.get('edx_video_id', None)
        old_dropdown_eid = old_metadata.get('edx_dropdown_video_id', None)
        new_dropdown_eid = new_metadata.get('edx_dropdown_video_id', None)

        if old_native_eid != new_native_eid and old_dropdown_eid != new_dropdown_eid:
            """Пользователь поменял оба поля. Мастер edx_dropdown_video_id, аргументацию см. выше"""
            master_dropdown(dropdown_eid)
            return

        if old_native_eid != new_native_eid:
            master_native(native_eid)
            return

        if old_dropdown_eid != new_dropdown_eid:
            master_dropdown(new_dropdown_eid)
            return

    def set_video_evms_values(self):
        """
        Добавляет список доступных edx_video_id в edx_dropdown_video_id
        :return:
        """
        turned_off_vals = lambda x: [
            {"display_name": u"'Update available video' option is turned off in course settings", "value": ""}]

        course = self.runtime.modulestore.get_course(self.location.course_key)
        get_ids = get_course_edx_val_ids
        if not course.update_from_evms:
            get_ids = turned_off_vals
        values = get_ids(course.id)

        if not values:
            values = [{"display_name": u"None", "value": ""}]

        if self.edx_video_id not in [v["value"] for v in values]:
            override = [
                {"display_name": self.edx_dropdown_video_overriden(self.edx_video_id), "value": self.edx_video_id}]
            values = override + values
        self.fields["edx_dropdown_video_id"]._values = values


def EVMS_editor_saved_dec(f):
    @wraps(f)
    def editor_saved(self, user, old_metadata, old_content):
        new_metadata = own_metadata(self)
        f(self, user, old_metadata, old_content)
        self.runtime.modulestore.update_item(self, user.id)
        self.synch_edx_id(old_metadata=old_metadata, new_metadata=new_metadata)
        self.save()
    return editor_saved