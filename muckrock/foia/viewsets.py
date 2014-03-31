"""
Viewsets for the FOIA API
"""

from django.core.mail import send_mail
from django.template.defaultfilters import slugify
from django.template.loader import render_to_string, get_template
from django.template import RequestContext

from datetime import datetime
from rest_framework import decorators, status as http_status, viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
import django_filters
import logging
import stripe

from muckrock.agency.models import Agency
from muckrock.foia.models import FOIARequest, FOIACommunication
from muckrock.foia.serializers import FOIARequestSerializer, FOIACommunicationSerializer, \
                                      FOIAPermissions, IsOwner
from muckrock.jurisdiction.models import Jurisdiction

# pylint: disable=R0901

logger = logging.getLogger(__name__)

class FOIARequestViewSet(viewsets.ModelViewSet):
    """API views for FOIARequest"""
    # pylint: disable=R0904
    # pylint: disable=C0103
    model = FOIARequest
    serializer_class = FOIARequestSerializer
    permission_classes = (FOIAPermissions,)

    class Filter(django_filters.FilterSet):
        """API Filter for FOIA Requests"""
        # pylint: disable=E1101
        # pylint: disable=R0903
        agency = django_filters.CharFilter(name='agency__name')
        jurisdiction = django_filters.CharFilter(name='jurisdiction__name')
        user = django_filters.CharFilter(name='user__username')
        tags = django_filters.CharFilter(name='tags__name')

        class Meta:
            model = FOIARequest
            fields = ('user', 'title', 'status', 'jurisdiction', 'agency', 'embargo', 'tags')

    filter_class = Filter

    def get_queryset(self):
        return FOIARequest.objects.get_viewable(self.request.user)

    def create(self, request):
        """Submit new request"""
        data = request.DATA
        try:
            jurisdiction = Jurisdiction.objects.get(pk=int(data['jurisdiction']))
            agency = Agency.objects.get(pk=int(data['agency']))
            if agency.jurisdiction != jurisdiction:
                raise ValueError

            requested_docs = data['document_request']
            template = get_template('request_templates/none.txt')
            context = RequestContext(request, {'title': data['title'],
                                               'document_request': requested_docs,
                                               'jurisdiction': jurisdiction})
            title, foia_request = \
                (s.strip() for s in template.render(context).split('\n', 1))


            slug = slugify(title) or 'untitled'
            foia = FOIARequest.objects.create(user=request.user, status='started', title=title,
                                              jurisdiction=jurisdiction, slug=slug,
                                              agency=agency, requested_docs=requested_docs,
                                              description=requested_docs)
            FOIACommunication.objects.create(
                    foia=foia, from_who=request.user.get_full_name(), to_who=foia.get_to_who(),
                    date=datetime.now(), response=False, full_html=False,
                    communication=foia_request)

            if request.user.get_profile().make_request():
                foia.submit()
                return Response({'status': 'FOI Request submitted',
                                 'Location': foia.get_absolute_url()},
                                 status=http_status.HTTP_201_CREATED)
            else:
                return Response({'status': 'Error - Out of requests.  FOI Request has been saved.',
                                 'Location': foia.get_absolute_url()},
                                 status=http_status.HTTP_402_PAYMENT_REQUIRED)

        except KeyError:
            return Response({'status': 'Missing data - Please supply title, document_request, '
                                       'jurisdiction, and agency'},
                             status=http_status.HTTP_400_BAD_REQUEST)
        except (ValueError, Jurisdiction.DoesNotExist, Agency.DoesNotExist):
            return Response({'status': 'Bad data - please supply jurisdiction and agency as the PK '
                                       'of existing entities.  Agency must be in Jurisdiction.'},
                             status=http_status.HTTP_400_BAD_REQUEST)

    @decorators.action(permission_classes=(IsOwner,))
    def followup(self, request, pk=None):
        """Followup on a request"""
        try:
            foia = FOIARequest.objects.get(pk=pk)
            self.check_object_permissions(request, foia)

            FOIACommunication.objects.create(
                foia=foia, from_who=request.user.get_full_name(), to_who=foia.get_to_who(),
                date=datetime.now(), response=False, full_html=False,
                communication=request.DATA['text'])

            appeal = request.DATA.get('appeal', False) and foia.is_appealable()
            foia.submit(appeal=appeal)

            if appeal:
                status = 'Appeal submitted'
            else:
                status = 'Follow up submitted'

            return Response({'status': status},
                             status=http_status.HTTP_200_OK)

        except FOIARequest.DoesNotExist:
            return Response({'status': 'Not Found'}, status=http_status.HTTP_404_NOT_FOUND)

        except KeyError:
            return Response({'status': 'Missing data - Please supply text for followup'},
                             status=http_status.HTTP_400_BAD_REQUEST)

    @decorators.action(permission_classes=(IsOwner,))
    def pay(self, request, pk=None):
        """Pay for a request"""
        try:
            foia = FOIARequest.objects.get(pk=pk)
            self.check_object_permissions(request, foia)
            if foia.status != 'payment':
                return Response({'status': 'Payment not required'},
                                status=http_status.HTTP_400_BAD_REQUEST)

            amount = int(foia.price * 105)
            request.user.get_profile().api_pay(amount,
                                               'Charge for request: %s %s' % (foia.title, foia.pk))

            foia.status = 'processed'
            foia.save()

            send_mail('[PAYMENT] Freedom of Information Request: %s' % (foia.title),
                      render_to_string('foia/admin_payment.txt',
                                       {'request': foia, 'amount': amount / 100.0}),
                      'info@muckrock.com', ['requests@muckrock.com'], fail_silently=False)

            logger.info('%s has paid %0.2f for request %s',
                        request.user.username, amount / 100.0, foia.title)

            return Response({'status': 'You have paid $%0.2f for the request' % (amount / 100.0)},
                             status=http_status.HTTP_200_OK)

        except FOIARequest.DoesNotExist:
            return Response({'status': 'Not Found'}, status=http_status.HTTP_404_NOT_FOUND)

        except stripe.CardError as exc:
            return Response({'status': 'Stripe Card Error: %s' % exc},
                            status=http_status.HTTP_400_BAD_REQUEST)

    @decorators.action(methods=['POST', 'DELETE'], permission_classes=(IsAuthenticated,))
    def follow(self, request, pk=None):
        """Follow or unfollow a request"""

        try:
            foia = FOIARequest.objects.get(pk=pk)
            self.check_object_permissions(request, foia)

            if foia.user == request.user:
                return Response({'status': 'You may not follow your own request'},
                                status=http_status.HTTP_400_BAD_REQUEST)

            if request.method == 'POST':
                foia.followed_by.add(request.user.get_profile())
                return Response({'status': 'Following'}, status=http_status.HTTP_200_OK)
            if request.method == 'DELETE':
                foia.followed_by.remove(request.user.get_profile())
                return Response({'status': 'Not following'}, status=http_status.HTTP_200_OK)

        except FOIARequest.DoesNotExist:
            return Response({'status': 'Not Found'}, status=http_status.HTTP_404_NOT_FOUND)

    def post_save(self, obj, created=False):
        if 'tags' in self.request.DATA:
            obj.tags.set(*self.request.DATA['tags'])
        return super(FOIARequestViewSet, self).post_save(obj, created=created)


class FOIACommunicationViewSet(viewsets.ModelViewSet):
    """API views for FOIARequest"""
    # pylint: disable=R0904
    # pylint: disable=C0103
    model = FOIACommunication
    serializer_class = FOIACommunicationSerializer
    permission_classes = (DjangoModelPermissions,)
