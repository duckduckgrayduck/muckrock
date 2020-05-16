# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2020-05-18 18:52
from __future__ import unicode_literals

# Django
from django.db import migrations

# Standard Library
import os

CLIENT_NAME = os.environ.get('CLIENT_NAME', 'muckrock')


def entitlements(apps, schema_editor):
    Organization = apps.get_model("organization", "Organization")
    Plan = apps.get_model("organization", "Plan")
    Entitlement = apps.get_model("organization", "Entitlement")

    for plan in Plan.objects.all():
        entitlement = Entitlement.objects.create(
            name=plan.name,
            slug="{}-{}".format(CLIENT_NAME, plan.slug),
            resources={
                'minimum_users': plan.minimum_users,
                'base_requests': plan.base_requests,
                'requests_per_user': plan.requests_per_user,
                'feature_level': plan.feature_level,
            }
        )
        Organization.objects.filter(plan=plan).update(entitlement=entitlement)


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0028_auto_20200512_1208'),
    ]

    operations = [
        migrations.RunPython(entitlements, migrations.RunPython.noop),
    ]
