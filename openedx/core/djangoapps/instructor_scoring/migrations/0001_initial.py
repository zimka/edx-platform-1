# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('courseware', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentGradeOverride',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('original_grade', models.IntegerField(default=0)),
                ('overridden_grade', models.IntegerField(default=0)),
                ('student_module', models.OneToOneField(on_delete=django.db.models.deletion.DO_NOTHING, to='courseware.StudentModule')),
            ],
        ),
    ]
