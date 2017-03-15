# coding: utf-8
import os
import logging
import yaml

from django.conf import settings
from xmodule.x_module import ResourceTemplates

log = logging.getLogger(__name__)
xmodule_templates_base_dir = lambda: settings.FEATURES.get('XMODULE_TEMPLATES_BASE_DIR')
#lambda чтобы избежать вызова settings до startup


class CustomResourceTemplates(ResourceTemplates):
    """
    Использовать для задания папки с шаблонами для x_module. Наследовать в x_module.XModuleDescriptor.
    Работает если определена FEATURES['XMODULE_TEMPLATES_BASE_DIR']
    Пример: FEATURES['XMODULE_TEMPLATES_BASE_DIR'] = '/edx/app/edxapp/edx-platform/templates_ru'
    """
    @staticmethod
    def base_templates_dir():
        xtbd = xmodule_templates_base_dir()
        if os.path.isdir(xtbd):
            return xtbd
        else:
            return None

    @classmethod
    def templates(cls):
        if not cls.base_templates_dir():
            return super(CustomResourceTemplates, cls).templates()

        templates = []
        dirname = cls.get_template_dir()
        if dirname is not None:
            if not os.path.isdir(dirname):
                    return templates
            for template_file in os.listdir(dirname):
                if not template_file.endswith('.yaml'):
                    log.warning("Skipping unknown template file %s", template_file)
                    continue
                template_content = open(os.path.join(dirname, template_file)).read()
                template = yaml.safe_load(template_content)
                template['template_id'] = template_file
                templates.append(template)
        return templates

    @classmethod
    def get_template_dir(cls):
        if not cls.base_templates_dir():
            return super(CustomResourceTemplates, cls).get_template_dir()

        if getattr(cls, 'template_dir_name', None):
            dirname = os.path.join(cls.base_templates_dir(), cls.template_dir_name)
            if not os.path.isdir(dirname):
                log.warning(u"No resource directory {dir} found when loading {cls_name} templates".format(
                    dir=dirname,
                    cls_name=cls.__name__,
                ))
                return None
            else:
                return dirname
        else:
            return None

    @classmethod
    def get_template(cls, template_id):
        if not cls.base_templates_dir():
            return super(CustomResourceTemplates, cls).get_template(cls)
        dirname = cls.get_template_dir()
        if dirname is not None:
            path = os.path.join(dirname, template_id)
            if os.path.exists(path):
                template_content = open(path).read()
                template = yaml.safe_load(template_content)
                template['template_id'] = template_id
                return template