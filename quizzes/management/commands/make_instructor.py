from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = "Grant an existing account instructor access without granting admin access."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, **options):
        try:
            user = get_user_model().objects.get(username=options["username"])
        except get_user_model().DoesNotExist:
            raise CommandError("That username does not exist. Register first.")
        group, _ = Group.objects.get_or_create(name="Instructors")
        user.groups.add(group)
        self.stdout.write(self.style.SUCCESS(f"{user.username} is now an instructor."))
