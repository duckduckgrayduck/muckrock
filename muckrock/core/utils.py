"""
Miscellanous utilities
"""

# Django
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.cache import cache, caches
from django.template import Context
from django.template.loader_tags import BlockNode, ExtendsNode

# Standard Library
import datetime
import logging
import random
import string
import sys
import time
import uuid

# Third Party
import actstream
import boto3
import requests
import stripe

logger = logging.getLogger(__name__)

# From http://stackoverflow.com/questions/2687173/django-how-can-i-get-a-block-from-a-template


class BlockNotFound(Exception):
    """Block not found exception"""


def get_node(template, context=Context(), name="subject"):
    """Render one block from a template"""
    for node in template:
        if isinstance(node, BlockNode) and node.name == name:
            return node.render(context)
        elif isinstance(node, ExtendsNode):
            return get_node(node.nodelist, context, name)
    raise BlockNotFound("Node '%s' could not be found in template." % name)


def new_action(
    actor, verb, action_object=None, target=None, public=True, description=None
):
    """Wrapper to send a new action and return the generated Action object."""
    # pylint: disable=too-many-arguments
    action_signal = actstream.action.send(
        actor,
        verb=verb,
        action_object=action_object,
        target=target,
        public=public,
        description=description,
    )
    # action_signal = ((action_handler, Action))
    return action_signal[0][1]


def generate_status_action(foia):
    """Generate activity stream action for agency response and return it."""
    if not foia.agency:
        return None
    verbs = {
        "rejected": "rejected",
        "done": "completed",
        "partial": "partially completed",
        "processed": "acknowledged",
        "no_docs": "has no responsive documents",
        "fix": "requires fix",
        "payment": "requires payment",
    }
    verb = verbs.get(foia.status, "is processing")
    return new_action(foia.agency, verb, target=foia)


def notify(users, action):
    """Notify a set of users about an action and return the list of notifications."""
    # pylint: disable=import-outside-toplevel
    # MuckRock
    from muckrock.accounts.models import Notification

    notifications = []
    if isinstance(users, Group):
        # If users is a group, get the queryset of users
        users = users.user_set.all()
    elif isinstance(users, User):
        # If users is a single user, make it into a list
        users = [users]
    if action is None:
        # If no action is provided, don't generate any notifications
        return notifications
    for user in users:
        notification = Notification.objects.create(user=user, action=action)
        notifications.append(notification)
    return notifications


def generate_key(size=12, chars=string.ascii_uppercase + string.digits):
    """Generates a random alphanumeric key"""
    return "".join(random.SystemRandom().choice(chars) for _ in range(size))


def get_stripe_token(card_number="4242424242424242"):
    """
    Helper function for creating a dummy Stripe token.
    Normally, the token would be generated by Stripe Checkout on the front end.
    Allows a different card number to be passed in to simulate different error cases.
    """
    card = {
        "number": card_number,
        "exp_month": datetime.date.today().month,
        "exp_year": datetime.date.today().year,
        "cvc": "123",
    }
    token = stripe_retry_on_error(stripe.Token.create, card=card, idempotency_key=True)
    # all we need for testing stripe calls is the token id
    return token.id


def cache_get_or_set(key, update, timeout):
    """Get the value from the cache if present, otherwise update it"""
    value = cache.get(key)
    if value is None:
        value = update()
        cache.set(key, value, timeout)
    return value


def retry_on_error(error, func, *args, **kwargs):
    """Retry a function on error"""
    max_retries = 10
    times = kwargs.pop("times", 0) + 1
    try:
        return func(*args, **kwargs)
    except error as exc:
        if times > max_retries:
            raise exc
        logger.warning(
            "Error, retrying #%d:\n\n%s", times, exc, exc_info=sys.exc_info()
        )
        return retry_on_error(error, func, times=times, *args, **kwargs)


def stripe_retry_on_error(func, *args, **kwargs):
    """Retry stripe API calls on connection errors"""
    if kwargs.get("idempotency_key") is True:
        kwargs["idempotency_key"] = uuid.uuid4().hex
    return retry_on_error(stripe.error.APIConnectionError, func, *args, **kwargs)


class TempDisconnectSignal:
    """Context manager to remporarily disable a signal"""

    def __init__(self, signal, receiver, sender, dispatch_uid=None):
        self.signal = signal
        self.receiver = receiver
        self.sender = sender
        self.dispatch_uid = dispatch_uid

    def __enter__(self):
        self.signal.disconnect(
            receiver=self.receiver, sender=self.sender, dispatch_uid=self.dispatch_uid
        )

    def __exit__(self, type_, value, traceback):
        self.signal.connect(
            receiver=self.receiver, sender=self.sender, dispatch_uid=self.dispatch_uid
        )


def read_in_chunks(file_, size=128):
    """Read a file in chunks"""
    # from https://www.smallsurething.com/how-to-read-a-file-properly-in-python/
    while True:
        chunk = file_.read(size)
        if not chunk:
            file_.close()
            break
        yield chunk


def get_squarelet_access_token():
    """Get an access token for squarelet"""

    lock_cache = caches["lock"]

    # if not in cache, lock, acquire token, put in cache
    access_token = lock_cache.get("squarelet_access_token")
    if access_token is None:
        with lock_cache.lock("squarelt_access_token"):
            access_token = lock_cache.get("squarelet_access_token")
            if access_token is None:
                token_url = "{}/openid/token".format(settings.SQUARELET_URL)
                auth = (
                    settings.SOCIAL_AUTH_SQUARELET_KEY,
                    settings.SOCIAL_AUTH_SQUARELET_SECRET,
                )
                data = {"grant_type": "client_credentials"}
                headers = {"X-Bypass-Rate-Limit": settings.BYPASS_RATE_LIMIT_SECRET}
                logger.info(token_url)
                resp = requests.post(token_url, data=data, auth=auth, headers=headers)
                resp.raise_for_status()
                resp_json = resp.json()
                access_token = resp_json["access_token"]
                # expire a few seconds early to ensure its not expired
                # when we try to use it
                expires_in = int(resp_json["expires_in"]) - 10
                lock_cache.set("squarelet_access_token", access_token, expires_in)
    return access_token


def _squarelet(method, path, **kwargs):
    """Helper function for squarelet requests"""
    api_url = "{}{}".format(settings.SQUARELET_URL, path)
    access_token = get_squarelet_access_token()
    headers = {
        "Authorization": "Bearer {}".format(access_token),
        "X-Bypass-Rate-Limit": settings.BYPASS_RATE_LIMIT_SECRET,
    }
    return method(api_url, headers=headers, **kwargs)


def squarelet_post(path, data):
    """Make a post request to squarlet"""
    return _squarelet(requests.post, path, data=data)


def squarelet_get(path, params=None):
    """Make a get request to squarlet"""
    if params is None:
        params = {}
    return _squarelet(requests.get, path, params=params)


def _zoho(method, path, **kwargs):
    """Helper function for zoho requests"""
    api_url = "{}{}".format(settings.ZOHO_URL, path)
    headers = {"Authorization": settings.ZOHO_TOKEN, "orgId": settings.ZOHO_ORG_ID}
    return method(api_url, headers=headers, **kwargs)


def zoho_post(path, json):
    """Make a post request to Zoho"""
    return _zoho(requests.post, path, json=json)


def zoho_get(path, params=None):
    """Make a post request to Zoho"""
    if params is None:
        params = {}
    return _zoho(requests.get, path, params=params)


def get_s3_storage_bucket():
    """Return the S3 storage bucket"""
    s3 = boto3.resource("s3")
    return s3.Bucket(settings.AWS_MEDIA_BUCKET_NAME)


def clear_cloudfront_cache(file_names):
    """Clear file from the cloudfront cache"""
    if not file_names:
        # invalidation fails if file names is empty
        return
    cloudfront = boto3.client("cloudfront")
    # find the current distribution
    distributions = [
        d
        for d in cloudfront.list_distributions()["DistributionList"]["Items"]
        if settings.AWS_S3_CUSTOM_DOMAIN in d["Aliases"]["Items"]
    ]
    if distributions:
        cloudfront.create_invalidation(
            DistributionId=distributions[0]["Id"],
            InvalidationBatch={
                "Paths": {
                    "Quantity": len(file_names),
                    "Items": ["/" + file for file in file_names],
                },
                "CallerReference": str(int(time.time())),
            },
        )


class UnclosableFile:
    """A wrapper for a file to make it unclosable"""

    def __init__(self, file_):
        self.file = file_

    def __getattr__(self, attr):
        return getattr(self.file, attr)

    def close(self):
        """Do not close the underlying file"""
