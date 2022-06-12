# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from mezzanine.core.admin import TabularDynamicInlineAdmin

from mezzy.utils.admin import LinkedAdminMixin, LinkedInlineMixin

from ..models import Category, Subcategory, Question


############
# Category #
############

class SubcategoryInlineAdmin(LinkedInlineMixin):
    """
    Inline admin with links to the complete subcategory admin.
    """
    count_field = "questions"
    link_text = _("Edit content and questions")
    model = Subcategory


@admin.register(Category)
class CategoryAdmin(LinkedAdminMixin):
    """
    Allows editing a category and its subcategories.
    """
    parent_field = "survey"
    fields = ["get_parent_link", "title", "description"]
    inlines = [SubcategoryInlineAdmin]


###############
# Subcategory #
###############

class QuestionInlineAdmin(TabularDynamicInlineAdmin):
    """
    Inline admin to edit individual questions.
    """
    model = Question


@admin.register(Subcategory)
class SubcategoryAdmin(LinkedAdminMixin):
    """
    Allows editing a subcategory and its questions.
    """
    parent_field = "category"
    fields = ["get_parent_link", "title", "description"]
    inlines = [QuestionInlineAdmin]
