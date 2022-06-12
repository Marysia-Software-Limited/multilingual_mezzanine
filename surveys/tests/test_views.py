from __future__ import absolute_import, unicode_literals

from builtins import range, zip

from django.contrib.auth.models import User
from django.test import TestCase

from django_dynamic_fixture import get

from mezzanine.core.models import CONTENT_STATUS_DRAFT, CONTENT_STATUS_PUBLISHED

from mezzy.utils.tests import ViewTestMixin

from surveys.models import (
    SurveyPage, SurveyPurchase, SurveyPurchaseCode, SurveyResponse, Category, Subcategory,
    Question, QuestionResponse)
from surveys.views import (
    SurveyPurchaseCreate, SurveyPurchaseDetail, SurveyResponseCreate, SurveyResponseComplete,
    SurveyPurchaseReport)


class SurveyPageTestCase(ViewTestMixin, TestCase):
    """
    Create a SurveyPage and user as fixtures.
    """

    @classmethod
    def setUpTestData(cls):
        super(SurveyPageTestCase, cls).setUpTestData()
        cls.USER = get(User, is_active=True, is_staff=False)
        cls.SURVEY = SurveyPage.objects.create(cost=10, max_rating=4)


class SurveyPurchaseCreateTestCase(SurveyPageTestCase):
    view = SurveyPurchaseCreate

    def test_access(self):
        survey = SurveyPage.objects.create()

        # Anon users cannot access surveys
        self.assertLoginRequired(self.view, slug=survey.slug)

        # Non-published pages cannot be accessed
        survey.status = CONTENT_STATUS_DRAFT
        survey.save()
        self.assert404(self.view, slug=survey.slug, user=self.USER)

        # Logged in users can access surveys
        survey.status = CONTENT_STATUS_PUBLISHED
        survey.save()
        self.assert200(self.view, slug=survey.slug, user=self.USER)

    def test_purchase_code(self):
        """
        Purchases completed with purchase codes.
        """
        valid_code = get(SurveyPurchaseCode, survey=self.SURVEY, uses_remaining=10)
        depleted_code = get(SurveyPurchaseCode, survey=self.SURVEY, uses_remaining=0)
        data = {}

        # Test invalid purchase code is rejected
        data["purchase_code"] = "invalid"
        self.post(self.view, slug=self.SURVEY.slug, user=self.USER, data=data)
        self.assertEqual(SurveyPurchase.objects.count(), 0)

        # Test depleted purchase code is rejected
        data["purchase_code"] = depleted_code.code
        self.post(self.view, slug=self.SURVEY.slug, user=self.USER, data=data)
        self.assertEqual(SurveyPurchase.objects.count(), 0)
        depleted_code.refresh_from_db()
        self.assertEqual(depleted_code.uses_remaining, 0)

        # Test valid code is accepted and purchase is created
        data["purchase_code"] = valid_code.code
        response = self.post(self.view, slug=self.SURVEY.slug, user=self.USER, data=data)
        purchase = SurveyPurchase.objects.get()
        self.assertEqual(response["location"], purchase.get_absolute_url())
        self.assertEqual(purchase.purchaser, self.USER)
        self.assertEqual(purchase.survey, self.SURVEY)
        self.assertEqual(purchase.transaction_id, valid_code.code)
        self.assertEqual(purchase.payment_method, "Purchase Code")
        self.assertEqual(purchase.amount, 0)

        # Test code uses have been reduced by 1
        valid_code.refresh_from_db()
        self.assertEqual(valid_code.uses_remaining, 9)

    def test_payment(self):
        """
        Purchases completed via the default payment method (doesn't do anything).
        """
        # Test the new purchase was created successfully
        response = self.post(self.view, slug=self.SURVEY.slug, user=self.USER)
        purchase = SurveyPurchase.objects.get()
        self.assertEqual(response["location"], purchase.get_absolute_url())
        self.assertEqual(purchase.purchaser, self.USER)
        self.assertEqual(purchase.survey, self.SURVEY)
        self.assertEqual(purchase.payment_method, "Complimentary")
        self.assertEqual(purchase.transaction_id, "Complimentary")
        self.assertEqual(purchase.amount, 0)  # Survey cost was None


class SurveyPurchaseDetailTestCase(SurveyPageTestCase):

    @classmethod
    def setUpTestData(cls):
        super(SurveyPurchaseDetailTestCase, cls).setUpTestData()
        cls.PURCHASE = get(
            SurveyPurchase, survey=cls.SURVEY, purchaser=cls.USER, purchased_with_code=None,
            report_generated=None)
        cls.PURCHASE_ID = str(cls.PURCHASE.public_id)

    def test_access(self):
        # Anon users cannot access the purchase
        self.assertLoginRequired(SurveyPurchaseDetail, public_id=self.PURCHASE_ID)

        # Non-owner users cannot access the purchase
        random_user = get(User, is_active=True)
        self.assertLoginRequired(
            SurveyPurchaseDetail, public_id=self.PURCHASE_ID, user=random_user)

        # Owner can access the purchase
        response = self.assert200(SurveyPurchaseDetail, public_id=self.PURCHASE_ID, user=self.USER)
        self.assertEqual(response.context_data["purchase"], self.PURCHASE)


class SurveyResponseCreateTestCase(SurveyPageTestCase):

    @classmethod
    def setUpTestData(cls):
        super(SurveyResponseCreateTestCase, cls).setUpTestData()
        cls.PURCHASE = get(
            SurveyPurchase, survey=cls.SURVEY, purchaser=cls.USER, purchased_with_code=None,
            report_generated=None)
        cls.PURCHASE_ID = str(cls.PURCHASE.public_id)

    def assertFieldError(self, response, field_key):
        """
        Verify a certain field in a form has an error.
        """
        form = response.context_data["form"]
        try:
            form.errors[field_key]
        except AttributeError:
            self.fail("The form '%s' doesn't contain any errors" % form)
        except KeyError:
            self.fail("The field '%s' doesn't contain any errors" % field_key)

    def test_access(self):
        # Add 5 questions to the survey
        for i in range(0, 5):
            get(Question, subcategory__category__survey=self.SURVEY)

        # Anon users can access the survey
        self.assert200(SurveyResponseCreate, public_id=self.PURCHASE_ID)

        # Logged-in users can access the survey
        response = self.assert200(SurveyResponseCreate, public_id=self.PURCHASE_ID, user=self.USER)

        # A form is present in the context with our 5 questions
        fields = response.context_data["form"].fields
        self.assertEqual(len(fields), 5)

    def test_survey_response(self):
        """
        Responses to questions in a survey are stored correctly.
        """
        # Create one text and two rating question
        text_question = get(
            Question, subcategory__category__survey=self.SURVEY, field_type=Question.TEXT_FIELD)
        rating_question = get(
            Question, subcategory__category__survey=self.SURVEY, field_type=Question.RATING_FIELD,
            required=True)
        inv_rating_question = get(
            Question, subcategory__category__survey=self.SURVEY, field_type=Question.RATING_FIELD,
            invert_rating=True)
        rating_field_key = "question_%s" % rating_question.pk
        data = {
            "question_%s" % text_question.pk: "TEST",
            "question_%s" % inv_rating_question.pk: self.SURVEY.max_rating,
        }

        # Rating field should provide choices according to the "max_rating" of the survey
        response = self.assert200(SurveyResponseCreate, public_id=self.PURCHASE_ID)
        choices = response.context_data["form"].fields[rating_field_key].choices
        self.assertEqual(len(choices), self.SURVEY.max_rating)

        # Required rating question should fail validation if not provided
        data[rating_field_key] = ""
        response = self.post(SurveyResponseCreate, public_id=self.PURCHASE_ID, data=data)
        self.assertFieldError(response, rating_field_key)
        self.assertEqual(SurveyResponse.objects.count(), 0)

        # Rating question should fail validation if value is above max_rating
        data[rating_field_key] = self.SURVEY.max_rating + 1
        response = self.post(SurveyResponseCreate, public_id=self.PURCHASE_ID, data=data)
        self.assertFieldError(response, rating_field_key)
        self.assertEqual(SurveyResponse.objects.count(), 0)

        # Rating question should fail validation if value is below 1
        data[rating_field_key] = 0
        response = self.post(SurveyResponseCreate, public_id=self.PURCHASE_ID, data=data)
        self.assertFieldError(response, rating_field_key)
        self.assertEqual(SurveyResponse.objects.count(), 0)

        # Rating question should fail validation if value is not numeric
        data[rating_field_key] = "abcd"
        response = self.post(SurveyResponseCreate, public_id=self.PURCHASE_ID, data=data)
        self.assertFieldError(response, rating_field_key)
        self.assertEqual(SurveyResponse.objects.count(), 0)

        # Rating question should pass validation if value is correct
        data[rating_field_key] = self.SURVEY.max_rating
        response = self.post(SurveyResponseCreate, public_id=self.PURCHASE_ID, data=data)
        survey_response = SurveyResponse.objects.get()

        # Verify the inverted rating question was in fact inverted
        inverted_response = QuestionResponse.objects.get(question=inv_rating_question)
        self.assertEqual(inverted_response.rating, 1)  # Inverted from SURVEY.max_rating
        self.assertEqual(inverted_response.text_response, "")
        self.assertEqual(inverted_response.response, survey_response)

        # Verify the rating response was stored correctly
        rating_response = QuestionResponse.objects.get(question=rating_question)
        self.assertEqual(rating_response.rating, self.SURVEY.max_rating)
        self.assertEqual(rating_response.text_response, "")
        self.assertEqual(rating_response.response, survey_response)

        # Verify the text response was stored correctly
        text_response = QuestionResponse.objects.get(question=text_question)
        self.assertIsNone(text_response.rating)
        self.assertEqual(text_response.text_response, "TEST")
        self.assertEqual(text_response.response, survey_response)

        # Verify we've been redirected to the confirmation message
        self.assertEqual(response["location"], self.PURCHASE.get_complete_url())

    def test_survey_response_complete(self):
        response = self.assert200(SurveyResponseComplete, public_id=self.PURCHASE.public_id)
        self.assertEqual(response.context_data["survey"], self.SURVEY)


class SurveyPurchaseReportTestCase(SurveyPageTestCase):

    def setUp(self):
        """
        Create a complex survey and submit responses to it.
        Data from the responses will then be tested for consistency.
        """
        super(SurveyPurchaseReportTestCase, self).setUp()
        self.purchase = get(
            SurveyPurchase, survey=self.SURVEY, purchaser=self.USER, purchased_with_code=None,
            report_generated=None)
        self.purchase_id = str(self.purchase.public_id)

        # Create 6 rating questions and 2 text questions
        # Distribute them in 2 categories and 3 subcategories
        category1 = get(Category, survey=self.SURVEY)
        subcategory1 = get(Subcategory, category=category1)
        get(Question, subcategory=subcategory1, field_type=Question.RATING_FIELD)
        get(Question, subcategory=subcategory1, field_type=Question.RATING_FIELD)
        subcategory2 = get(Subcategory, category=category1)
        get(Question, subcategory=subcategory2, field_type=Question.RATING_FIELD)
        get(Question, subcategory=subcategory2, field_type=Question.RATING_FIELD)

        category2 = get(Category, survey=self.SURVEY)
        subcategory3 = get(Subcategory, category=category2)
        get(Question, subcategory=subcategory3, field_type=Question.RATING_FIELD)
        get(Question, subcategory=subcategory3, field_type=Question.RATING_FIELD)
        get(Question, subcategory=subcategory3, field_type=Question.TEXT_FIELD)
        get(Question, subcategory=subcategory3, field_type=Question.TEXT_FIELD)

        # Create 3 SurveyResponses with 8 QuestionResponses each (24 total)
        # This data will be checked in test_report()
        questions = self.SURVEY.get_questions()
        response_values = [
            [1, 2, 3, 4, 1, 4, "Text 1", "Text 2"],
            [1, 2, 3, 4, 2, 3, "Text 3", "Text 4"],
            [1, 2, 3, 4, 3, 2, "Text 5", "Text 6"],
        ]
        for value_list in response_values:
            survey_response = get(SurveyResponse, purchase=self.purchase)
            question_responses = []
            for question, value in zip(questions, value_list):
                question_responses.append(QuestionResponse(
                    question=question, response=survey_response,
                    rating=value if question.field_type == Question.RATING_FIELD else None,
                    text_response=value if question.field_type == Question.TEXT_FIELD else ""))
            QuestionResponse.objects.bulk_create(question_responses)

        # Create some more responses on another SurveyPurchase but the same SurveyPage
        # This shouldn't affect the data on the SurveyPurchase we are testing
        for i in range(0, 10):
            get(QuestionResponse,
                rating=4,
                question__subcategory__category__survey=self.SURVEY,
                response__purchase__survey=self.SURVEY)

    def test_access(self):
        # Anon users cannot access the report
        self.assertLoginRequired(SurveyPurchaseReport, public_id=self.purchase_id)

        # Logged-in users can access the report
        response = self.assert200(SurveyPurchaseReport, public_id=self.purchase_id, user=self.USER)

        # The report should be empty
        self.assertEqual(response.context_data["purchase"].get_report_as_json(), [])

    def test_report(self):
        """
        The report should be generated when POSTing to the view.
        It should then be retrievable via GET.
        """
        # POST the form to generate the report
        response = self.post(SurveyPurchaseReport, public_id=self.purchase_id, user=self.USER)
        self.assertEqual(response["location"], self.purchase.get_report_url())

        # GET the page and verify all the report data
        # The report data is based on the QuestionResponses added in setUp()
        response = self.assert200(
            SurveyPurchaseReport, public_id=self.purchase_id, user=self.USER)
        report = response.context_data["purchase"].get_report_as_json()
        self.assertEqual(report["rating"]["count"], 18)
        self.assertEqual(report["rating"]["average"], 2.5)
        self.assertListEqual(report["rating"]["frequencies"], [[1, 4], [2, 5], [3, 5], [4, 4]])

        # Category 1
        cat1 = report["categories"][0]
        self.assertEqual(cat1["rating"]["count"], 12)
        self.assertEqual(cat1["rating"]["average"], 2.5)
        self.assertListEqual(cat1["rating"]["frequencies"], [[1, 3], [2, 3], [3, 3], [4, 3]])

        # Subcategory 1
        sub1 = cat1["subcategories"][0]
        self.assertEqual(sub1["rating"]["count"], 6)
        self.assertEqual(sub1["rating"]["average"], 1.5)
        self.assertListEqual(sub1["rating"]["frequencies"], [[1, 3], [2, 3], [3, 0], [4, 0]])

        # Question 1
        q1 = sub1["questions"][0]
        self.assertEqual(q1["rating"]["count"], 3)
        self.assertEqual(q1["rating"]["average"], 1)
        self.assertListEqual(q1["rating"]["frequencies"], [[1, 3], [2, 0], [3, 0], [4, 0]])

        # Question 2
        q2 = sub1["questions"][1]
        self.assertEqual(q2["rating"]["count"], 3)
        self.assertEqual(q2["rating"]["average"], 2)
        self.assertListEqual(q2["rating"]["frequencies"], [[1, 0], [2, 3], [3, 0], [4, 0]])

        # Subcategory 2
        sub2 = cat1["subcategories"][1]
        self.assertEqual(sub2["rating"]["count"], 6)
        self.assertEqual(sub2["rating"]["average"], 3.5)
        self.assertListEqual(sub2["rating"]["frequencies"], [[1, 0], [2, 0], [3, 3], [4, 3]])

        # Question 3
        q3 = sub2["questions"][0]
        self.assertEqual(q3["rating"]["count"], 3)
        self.assertEqual(q3["rating"]["average"], 3)
        self.assertListEqual(q3["rating"]["frequencies"], [[1, 0], [2, 0], [3, 3], [4, 0]])

        # Question 4
        q4 = sub2["questions"][1]
        self.assertEqual(q4["rating"]["count"], 3)
        self.assertEqual(q4["rating"]["average"], 4)
        self.assertListEqual(q4["rating"]["frequencies"], [[1, 0], [2, 0], [3, 0], [4, 3]])

        # Category 2
        cat2 = report["categories"][1]
        self.assertEqual(cat2["rating"]["count"], 6)
        self.assertEqual(cat2["rating"]["average"], 2.5)
        self.assertListEqual(cat2["rating"]["frequencies"], [[1, 1], [2, 2], [3, 2], [4, 1]])

        # Subcategory 3
        sub3 = cat2["subcategories"][0]
        self.assertEqual(sub3["rating"]["count"], 6)
        self.assertEqual(sub3["rating"]["average"], 2.5)
        self.assertListEqual(sub3["rating"]["frequencies"], [[1, 1], [2, 2], [3, 2], [4, 1]])

        # Question 5
        q5 = sub3["questions"][0]
        self.assertEqual(q5["rating"]["count"], 3)
        self.assertEqual(q5["rating"]["average"], 2)
        self.assertListEqual(q5["rating"]["frequencies"], [[1, 1], [2, 1], [3, 1], [4, 0]])

        # Question 6
        q6 = sub3["questions"][1]
        self.assertEqual(q6["rating"]["count"], 3)
        self.assertEqual(q6["rating"]["average"], 3)
        self.assertListEqual(q6["rating"]["frequencies"], [[1, 0], [2, 1], [3, 1], [4, 1]])

        # Subcategory 3 should NOT have a 3rd and 4th question because those are text-only
        with self.assertRaises(IndexError):
            sub3["questions"][2]
            sub3["questions"][3]

        # Question 7
        q7 = report["text_questions"][0]
        self.assertListEqual(q7["responses"], ["Text 1", "Text 3", "Text 5"])

        # Question 8
        q8 = report["text_questions"][1]
        self.assertListEqual(q8["responses"], ["Text 2", "Text 4", "Text 6"])
