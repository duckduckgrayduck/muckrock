"""
Composer model for the FOIA application

This represents a draft request before it is sent.  By selecting multiple
agencies, it is possible to use this to submit a multi-request.  After
submission, the composer stays around to tie together multi-requests and to
serve as the basis for cloning.  This also enables future planned features and
upgrades, such as recurring requests.
"""

# Django
from celery import current_app
from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.db import models, transaction
from django.utils import timezone
from django.utils.text import slugify

# Standard Library
from datetime import timedelta
from itertools import izip_longest

# Third Party
from taggit.managers import TaggableManager

# MuckRock
from muckrock.accounts.models import Profile
from muckrock.foia.constants import COMPOSER_EDIT_DELAY, COMPOSER_SUBMIT_DELAY
from muckrock.foia.models import FOIARequest
from muckrock.foia.querysets import FOIAComposerQuerySet
from muckrock.organization.models import Organization
from muckrock.tags.models import TaggedItemBase

STATUS = [
    ('started', 'Draft'),
    ('submitted', 'Processing'),
    ('filed', 'Filed'),
]


class FOIAComposer(models.Model):
    """A FOIA request composer"""
    # pylint: disable=too-many-instance-attributes

    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='composers',
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    status = models.CharField(max_length=10, choices=STATUS, default='started')
    agencies = models.ManyToManyField('agency.Agency', related_name='composers')
    requested_docs = models.TextField(blank=True)
    edited_boilerplate = models.BooleanField(default=False)
    datetime_created = models.DateTimeField(default=timezone.now, db_index=True)
    datetime_submitted = models.DateTimeField(
        blank=True,
        null=True,
        db_index=True,
    )
    embargo = models.BooleanField(default=False)
    permanent_embargo = models.BooleanField(default=False)
    parent = models.ForeignKey(
        'self',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        help_text='The composer this was cloned from, if cloned',
    )

    # for refunding requests if necessary
    num_org_requests = models.PositiveSmallIntegerField(default=0)
    num_monthly_requests = models.PositiveSmallIntegerField(default=0)
    num_reg_requests = models.PositiveSmallIntegerField(default=0)

    # for delayed submission
    delayed_id = models.CharField(blank=True, max_length=255)

    objects = FOIAComposerQuerySet.as_manager()
    tags = TaggableManager(through=TaggedItemBase, blank=True)

    class Meta:
        verbose_name = 'FOIA Composer'
        permissions = (('view_foiacomposer', 'Can view this composer'),)

    def __unicode__(self):
        return self.title

    def save(self, *args, **kwargs):
        """Set title and slug on save"""
        self.title = self.title.strip() or 'Untitled'
        self.slug = slugify(self.title) or 'untitled'
        super(FOIAComposer, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Resolve any pending new agency tasks"""
        for agency in self.agencies.filter(status='pending'):
            if agency.composers.count() == 1:
                agency.delete()
        super(FOIAComposer, self).delete(*args, **kwargs)

    def get_absolute_url(self):
        """The url for this object"""
        return reverse(
            'foia-composer-detail', kwargs={
                'slug': self.slug,
                'idx': self.pk,
            }
        )

    def submit(self, contact_info=None):
        """Submit a composer to create the requests"""
        from muckrock.foia.tasks import submit_composer

        num_requests = self.agencies.count()
        request_count = self.user.profile.make_requests(num_requests)
        self.num_reg_requests = request_count['regular']
        self.num_monthly_requests = request_count['monthly']
        self.num_org_requests = request_count['org']
        self.status = 'submitted'
        self.datetime_submitted = timezone.now()
        for agency in self.agencies.select_related(
            'jurisdiction__law',
            'jurisdiction__parent__law',
        ).iterator():
            FOIARequest.objects.create_new(
                composer=self,
                agency=agency,
            )
        # if num_requests is less than the multi-review amount, we will approve
        # the request right away, other wise we create a multirequest task
        approve = num_requests < settings.MULTI_REVIEW_AMOUNT
        result = submit_composer.apply_async(
            args=(self.pk, approve, contact_info),
            countdown=COMPOSER_SUBMIT_DELAY,
        )
        self.delayed_id = result.id
        self.save()

    def approved(self, contact_info=None):
        """A pending composer is approved for sending to the agencies"""
        for foia in self.foias.all():
            foia.submit(contact_info=contact_info)
        self.status = 'filed'
        self.save()

    def has_perm(self, user, perm):
        """Short cut for checking a FOIA composer permission"""
        return user.has_perm('foia.%s_foiacomposer' % perm, self)

    def return_requests(self, num_requests=None):
        """Return requests to the composer's author"""
        if num_requests is None:
            # if no num_requests passed in, refund all requests
            return_amts = {
                'regular': self.num_reg_requests,
                'monthly': self.num_monthly_requests,
                'org': self.num_org_requests,
            }
        else:
            return_amts = self._calc_return_requests(num_requests)

        self._return_requests(return_amts)

    def _return_requests(self, return_amts):
        """Helper method for return requests
        Does the actually returning
        """
        with transaction.atomic():
            self.num_reg_requests -= min(
                return_amts['regular'], self.num_reg_requests
            )
            self.num_monthly_requests -= min(
                return_amts['monthly'], self.num_monthly_requests
            )
            self.num_org_requests -= min(
                return_amts['org'], self.num_org_requests
            )
            self.save()

            # add the return requests to the user's profile
            profile = (
                Profile.objects.select_for_update()
                .get(pk=self.user.profile.id)
            )
            profile.num_requests += return_amts['regular']
            profile.get_monthly_requests()
            profile.monthly_requests += return_amts['monthly']
            if profile.organization:
                org = (
                    Organization.objects.select_for_update().get(
                        pk=profile.organization.pk
                    )
                )
                org.get_requests()
                org.num_requests += return_amts['org']
                org.save()
            else:
                profile.monthly_requests += return_amts['org']
            profile.save()

    def _calc_return_requests(self, num_requests):
        """Determine how many of each type of request to return"""
        used = [
            self.num_reg_requests,
            self.num_monthly_requests,
            self.num_org_requests,
        ]
        ret = []
        while num_requests:
            try:
                num_used = used.pop(0)
            except IndexError:
                ret.append(num_requests)
                break
            else:
                num_ret = min(num_used, num_requests)
                num_requests -= num_ret
                ret.append(num_ret)
        ret_dict = dict(
            izip_longest(
                ['regular', 'monthly', 'org', 'extra'],
                ret,
                fillvalue=0,
            )
        )
        ret_dict['regular'] += ret_dict.pop('extra')
        return ret_dict

    def revokable(self):
        """Is this composer revokable?"""
        return (
            self.delayed_id != '' and self.datetime_submitted <
            timezone.now() + timedelta(seconds=COMPOSER_EDIT_DELAY)
            and self.status == 'submitted'
        )

    def revoke(self):
        """Revoke a submitted composer"""
        current_app.control.revoke(self.delayed_id)
        self.status = 'started'
        self.delayed_id = ''
        self.datetime_submitted = None
        self.foias.all().delete()
        self.return_requests()
        self.save()
