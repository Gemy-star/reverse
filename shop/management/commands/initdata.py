# -*- coding: utf-8 -*-
from django.contrib.auth.models import Group
from shop.models import ReverseUser
from django.core.management.base import BaseCommand

from shop.consts import DefaultSuperUser, Groups


class Command(BaseCommand):
    help = "Initialize default data"

    def handle(self, *args, **options):
        # User Groups Check and Create
        for group in Groups:
            _, created = Group.objects.get_or_create(name=group.value)
            if created:
                self.stdout.write(self.style.NOTICE(f"Create user group '{group.value}' in database"))
        if ReverseUser.objects.count() == 0:
            self.stdout.write(
                self.style.NOTICE(
                    f"User database is empty, creating a default superuser: {DefaultSuperUser.NAME} / {DefaultSuperUser.PASSWORD}"
                )
            )
            ReverseUser.objects.create_superuser(DefaultSuperUser.NAME, DefaultSuperUser.EMAIL, DefaultSuperUser.PASSWORD , is_customer=False)
