from __future__ import absolute_import, unicode_literals

from django.test import override_settings

from unittest import skipUnless

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

try:
    import authorize  # noqa
    AUTHORIZENET_INSTALLED = True
except ImportError:
    AUTHORIZENET_INSTALLED = False

from . import test_views
from surveys.models import SurveyPage, SurveyPurchase


@skipUnless(AUTHORIZENET_INSTALLED, "py-authorize not installed")
@override_settings(AUTHORIZE_NET_LOGIN="")
@override_settings(AUTHORIZE_NET_TRANS_KEY="")
class AuthorizenetTestCase(test_views.SurveyPurchaseCreateTestCase):
    """
    Test the payment is processed correctly by Authorize.net.
    Since we are inheriting from an existing test case, the Authorize.net view
    will also be tested for purchase code orders.
    """

    def setUp(self):
        """
        Execute the imports here so they don't run if py-authorize is not installed.
        """
        super(AuthorizenetTestCase, self).setUp()
        from surveys.payments.authorizenet import AuthorizenetSurveyPurchaseCreate
        self.view = AuthorizenetSurveyPurchaseCreate

    @patch("surveys.payments.authorizenet.authorize")
    def test_payment(self, authorize_mock):
        """
        Test credit card fields are required and Authorize.net API is called.
        """
        # The form should raise errors if the 3 card fields are not provided
        data = {"card_number": "", "card_expiry": "", "card_ccv": ""}
        response = self.post(self.view, slug=self.SURVEY.slug, user=self.USER, data=data)
        self.assertEqual(len(response.context_data["form"].errors), 3)
        self.assertEqual(SurveyPurchase.objects.count(), 0)

        # The payment should go through if all details are provided
        # Notice we're mocking the "authorize" package, so no validation is performed
        data = {"card_number": "1", "card_expiry": "1", "card_ccv": "1"}
        response = self.post(self.view, slug=self.SURVEY.slug, user=self.USER, data=data)
        purchase = SurveyPurchase.objects.get()
        self.assertEqual(response["location"], purchase.get_absolute_url())
        self.assertEqual(purchase.purchaser, self.USER)
        self.assertEqual(purchase.survey, self.SURVEY)
        self.assertEqual(purchase.payment_method, "Authorize.Net")
        self.assertEqual(purchase.amount, self.SURVEY.cost)

        # Verify our mock was called like we would call the API
        authorize_mock.Transaction.sale.assert_called_once()

    def test_free_survey_skips_payment(self):
        """
        Free surveys should bypass Authorize.net altogether.
        """
        free_survey = SurveyPage.objects.create(cost=0)

        # Purchase should be created without providing any credit card data
        self.post(self.view, slug=free_survey.slug, user=self.USER)
        purchase = SurveyPurchase.objects.get()
        self.assertEqual(purchase.purchaser, self.USER)
        self.assertEqual(purchase.survey, free_survey)
        self.assertEqual(purchase.payment_method, "Complimentary")
        self.assertEqual(purchase.transaction_id, "Complimentary")
        self.assertEqual(purchase.amount, 0)
