# -*- coding: utf-8 -*-
# Generated by Django 1.9.9 on 2017-03-20 21:27


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('foia', '0025_auto_20170301_2035'),
    ]

    operations = [
        migrations.AlterField(
            model_name='foiarequest',
            name='email',
            field=models.CharField(blank=True, max_length=254),
        ),
    ]
