from __future__ import absolute_import, unicode_literals

from django.contrib.auth.models import User
from django.test import TestCase

from django_dynamic_fixture import get

from surveys.models import SurveyPage, SurveyPurchase


class BaseSurveyPageTest(TestCase):
    """
    Create a SurveyPage and user as fixtures.
    """

    @classmethod
    def setUpTestData(cls):
        super(BaseSurveyPageTest, cls).setUpTestData()
        cls.USER = get(User, is_active=True, is_staff=False)
        cls.SURVEY = SurveyPage.objects.create(cost=10, max_rating=4)


class SurveyPurchaseTestCase(BaseSurveyPageTest):

    def test_manager(self):
        kwargs = {"survey": self.SURVEY, "report_generated": None}

        # Create 3 open purchases for the user
        purchases = [
            get(SurveyPurchase, purchaser=self.USER, **kwargs),
            get(SurveyPurchase, purchaser=self.USER, **kwargs),
            get(SurveyPurchase, purchaser=self.USER, **kwargs),
        ]
        # Create some other purchases for other users
        get(SurveyPurchase, **kwargs)
        get(SurveyPurchase, **kwargs)
        get(SurveyPurchase, **kwargs)

        # Test all purchases are open before any reports are generated
        self.assertEqual(SurveyPurchase.objects.open().count(), 6)
        self.assertEqual(SurveyPurchase.objects.closed().count(), 0)
        self.assertEqual(self.USER.survey_purchases.open().count(), 3)
        self.assertEqual(self.USER.survey_purchases.closed().count(), 0)

        # The first purchase should be closed once the report is generated
        purchases[0].generate_report()
        self.assertEqual(SurveyPurchase.objects.open().count(), 5)
        self.assertEqual(SurveyPurchase.objects.closed().count(), 1)
        self.assertEqual(self.USER.survey_purchases.open().count(), 2)
        self.assertEqual(self.USER.survey_purchases.closed()[0], purchases[0])
