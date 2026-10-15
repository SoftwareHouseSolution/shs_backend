"""Users and groups in the admin's own style.

django.contrib.auth registers User and Group with Django's stock ModelAdmin, whose inputs
carry none of Unfold's styling. They are registered again here on Unfold's ModelAdmin and
its user forms, so these pages look and behave like the rest of the admin.
"""

from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from .admin_utils import DirectionalInputsMixin

admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(DirectionalInputsMixin, BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    list_per_page = 50
    warn_unsaved_form = True


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    list_per_page = 50
    warn_unsaved_form = True
