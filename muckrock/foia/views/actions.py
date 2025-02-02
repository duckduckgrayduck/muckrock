"""
FOIA views for actions
"""

# Django
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

# Standard Library
import logging
from datetime import timedelta

# Third Party
import actstream

# MuckRock
from muckrock.accounts.utils import mixpanel_event
from muckrock.core.utils import new_action
from muckrock.crowdfund.forms import CrowdfundForm
from muckrock.foia.forms import FOIAEmbargoForm
from muckrock.foia.models import END_STATUS, FOIARequest

logger = logging.getLogger(__name__)


@login_required
def embargo(request, jurisdiction, jidx, slug, idx):
    """Change the embargo on a request"""

    def fine_tune_embargo(request, foia):
        """Adds an expiration date or makes permanent if necessary."""
        form = FOIAEmbargoForm(
            {
                "permanent_embargo": request.POST.get("permanent_embargo"),
                "date_embargo": request.POST.get("date_embargo"),
            }
        )
        if form.is_valid():
            permanent = form.cleaned_data["permanent_embargo"]
            expiration = form.cleaned_data["date_embargo"]
            if foia.has_perm(request.user, "embargo_perm"):
                foia.permanent_embargo = permanent
            if expiration and foia.status in END_STATUS:
                foia.date_embargo = expiration
            foia.save(comment="updated embargo")

    def create_embargo(request, foia):
        """Apply an embargo to the FOIA"""
        if foia.has_perm(request.user, "embargo"):
            foia.embargo = True
            foia.save(comment="added embargo")
            logger.info("%s embargoed %s", request.user, foia)
            new_action(request.user, "embargoed", target=foia)
            fine_tune_embargo(request, foia)
        else:
            logger.error("%s was forbidden from embargoing %s", request.user, foia)
            messages.error(request, "You cannot embargo requests.")

    def update_embargo(request, foia):
        """Update an embargo to the FOIA"""
        if foia.has_perm(request.user, "embargo"):
            fine_tune_embargo(request, foia)
        else:
            logger.error(
                "%s was forbidden from updating the embargo on %s", request.user, foia
            )
            messages.error(request, "You cannot update this embargo.")

    def delete_embargo(request, foia):
        """Remove an embargo from the FOIA"""
        foia.embargo = False
        foia.save(comment="removed embargo")
        logger.info("%s unembargoed %s", request.user, foia)
        new_action(request.user, "unembargoed", target=foia)

    foia = get_object_or_404(
        FOIARequest,
        agency__jurisdiction__slug=jurisdiction,
        agency__jurisdiction__pk=jidx,
        slug=slug,
        pk=idx,
    )
    has_perm = foia.has_perm(request.user, "change")
    if request.method == "POST" and has_perm:
        embargo_action = request.POST.get("embargo")
        if embargo_action == "create":
            create_embargo(request, foia)
        elif embargo_action == "update":
            update_embargo(request, foia)
        elif embargo_action == "delete":
            delete_embargo(request, foia)
    return redirect(foia)


@login_required
def follow(request, jurisdiction, jidx, slug, idx):
    """Follow or unfollow a request"""
    foia = get_object_or_404(
        FOIARequest,
        agency__jurisdiction__slug=jurisdiction,
        agency__jurisdiction__pk=jidx,
        slug=slug,
        pk=idx,
    )
    if actstream.actions.is_following(request.user, foia):
        actstream.actions.unfollow(request.user, foia)
        messages.success(request, "You are no longer following this request.")
        mixpanel_event(request, "Unfollow", foia.mixpanel_data())
    else:
        actstream.actions.follow(request.user, foia, actor_only=False)
        messages.success(request, "You are now following this request.")
        mixpanel_event(request, "Follow", foia.mixpanel_data())
    return redirect(foia)


@login_required
def toggle_autofollowups(request, jurisdiction, jidx, slug, idx):
    """Toggle autofollowups"""
    foia = get_object_or_404(
        FOIARequest,
        agency__jurisdiction__slug=jurisdiction,
        agency__jurisdiction__pk=jidx,
        slug=slug,
        pk=idx,
    )

    if foia.has_perm(request.user, "change"):
        foia.disable_autofollowups = not foia.disable_autofollowups
        foia.save(comment="toggled autofollowups")
        action = "disabled" if foia.disable_autofollowups else "enabled"
        msg = "Autofollowups have been %s" % action
        messages.success(request, msg)
    else:
        msg = "You must own the request to toggle auto-followups."
        messages.error(request, msg)
    return redirect(foia)


# Staff Actions
@transaction.atomic
@login_required
def crowdfund_request(request, idx, **kwargs):
    """Crowdfund a request"""
    # select for update locks this request in order to prevent a race condition
    # allowing multiple crowdfunds to be created for it
    foia = get_object_or_404(
        FOIARequest.objects.select_for_update().select_related(
            "agency__jurisdiction", "composer"
        ),
        pk=idx,
    )
    # check for unauthorized access
    if not foia.has_perm(request.user, "crowdfund"):
        messages.error(request, "You may not crowdfund this request.")
        return redirect(foia)
    if request.method == "POST":
        # save crowdfund object
        form = CrowdfundForm(request.POST)
        if form.is_valid():
            crowdfund = form.save()
            foia.crowdfund = crowdfund
            foia.save(comment="added a crowdfund")
            messages.success(request, "Your crowdfund has started, spread the word!")
            new_action(
                request.user, "began crowdfunding", action_object=crowdfund, target=foia
            )
            crowdfund.send_intro_email(request.user)
            mixpanel_event(
                request,
                "Launch Request Crowdfund",
                foia.mixpanel_data(
                    {
                        "Name": crowdfund.name,
                        "Payment Capped": crowdfund.payment_capped,
                        "Payment Required": float(crowdfund.payment_required),
                        "Date Due": crowdfund.date_due.isoformat(),
                    }
                ),
            )
            return redirect(foia)

    elif request.method == "GET":
        # create crowdfund form
        default_crowdfund_duration = 30
        date_due = timezone.now() + timedelta(default_crowdfund_duration)
        initial = {
            "name": "Crowdfund Request: %s" % str(foia),
            "description": "Help cover the request fees needed to free these docs!",
            "payment_required": foia.get_stripe_amount(),
            "date_due": date_due,
            "foia": foia,
        }
        form = CrowdfundForm(initial=initial)
        mixpanel_event(request, "Start Request Crowdfund", foia.mixpanel_data())

    return render(request, "forms/foia/crowdfund.html", {"form": form})
