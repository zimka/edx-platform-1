# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('courseware', '0001_initial'),
        ('instructor_scoring', '0005_studentcourseresultoverride_whitelist'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentGradeOverwrite',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('original_grade', models.FloatField(default=0)),
                ('current_grade', models.FloatField(default=0)),
                ('student_module', models.OneToOneField(on_delete=django.db.models.deletion.DO_NOTHING, to='courseware.StudentModule')),
            ],
        ),
        migrations.RemoveField(
            model_name='studentgradeoverride',
            name='student_module',
        ),
        migrations.DeleteModel(
            name='StudentGradeOverride',
        ),
    ]
