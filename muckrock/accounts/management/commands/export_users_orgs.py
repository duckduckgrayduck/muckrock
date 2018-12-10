"""
Management command to export users and organizations for squarelet
"""
# Django
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

# Third Party
import unicodecsv as csv

# MuckRock
from muckrock.organization.models import Membership, Organization

# XXX what to do with agency users?


class Command(BaseCommand):
    """
    Command to export all users and organizations for importing into squarelet

    This is intended to be a one time use script for the initial migration to
    squarelet
    """

    def handle(self, *args, **kwargs):
        # pylint: disable=unused-argument
        with transaction.atomic():
            self.export_users()
            self.export_orgs()
            self.export_members()

    def export_users(self):
        """Export users"""
        with open('users.csv', 'wb') as out_file:
            writer = csv.writer(out_file)
            writer.writerow([
                'uuid',
                'username',
                'email',
                'password',
                'full_name',
                'is_staff',
                'is_active',
                'is_superuser',
                'email_confirmed',
            ])
            for user in User.objects.select_related('profile').exclude(
                profile__acct_type='agency'
            ):
                writer.writerow([
                    user.profile.uuid,
                    user.username,
                    user.email,
                    user.password,
                    user.profile.full_name,
                    user.is_staff,
                    user.is_active,
                    user.is_superuser,
                    user.profile.email_confirmed,
                ])

    def export_orgs(self):
        """Export organizations"""
        # pylint: disable=protected-access
        with open('orgs.csv', 'wb') as out_file:
            writer = csv.writer(out_file)
            writer.writerow([
                'uuid',
                'name',
                'type',
                'individual',
                'private',
                'customer_id',
                'subscription_id',
                'date_update',
                'num_requests',
                'max_users',
                'monthly_cost',
                'monthly_requests',
            ])
            for org in Organization.objects.select_related(
                'owner__profile'
            ).exclude(
                individual=True, users__profile__acct_type='agency'
            ):
                writer.writerow([
                    org.uuid,
                    org.name,
                    org.org_type,
                    org.individual,
                    org.private,
                    org.owner.profile.customer_id,
                    org.stripe_id,
                    org.date_update,
                    org.num_requests,
                    org.max_users,
                    org.monthly_cost,
                    org._monthly_requests,
                ])

    def export_members(self):
        """Export memberships"""
        with open('members.csv', 'wb') as out_file:
            writer = csv.writer(out_file)
            writer.writerow([
                'user_uuid',
                'org_uuid',
                'user_username',
                'org_name',
                'is_admin',
            ])
            for member in Membership.objects.select_related(
                'user__profile', 'organization'
            ).exclude(user__profile__acct_type='agency'):
                writer.writerow([
                    member.user.profile.uuid,
                    member.organization.uuid,
                    member.user.username,
                    member.organization.name,
                    member.organization.owner == member.user,
                ])
