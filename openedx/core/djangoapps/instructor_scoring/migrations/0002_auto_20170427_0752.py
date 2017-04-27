# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('student_grade_override', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='studentgradeoverride',
            old_name='overridden_grade',
            new_name='current_grade',
        ),
    ]
