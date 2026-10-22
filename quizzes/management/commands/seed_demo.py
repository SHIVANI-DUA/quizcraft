from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import transaction
from quizzes.models import Quiz
from quizzes.serializers import QuizWriteSerializer

class Command(BaseCommand):
    help = "Create an idempotent sample quiz; no demo login or shared password is created."

    @transaction.atomic
    def handle(self, *args, **options):
        call_command("seed_python_quiz")
        owner, created = get_user_model().objects.get_or_create(username="quiz_demo_author", defaults={"is_active": False})
        if created:
            owner.set_unusable_password()
            owner.save()
        title = "Python & Django essentials"
        if Quiz.objects.filter(owner=owner, title=title).exists():
            self.stdout.write("Sample quiz already exists.")
            return
        data = {"title": title, "description": "Warm up with five questions about Python, Django, and REST APIs.",
                "category": "Development", "is_published": True, "questions": []}
        examples = [
            ("Which Python type is immutable?", ["List", "Dictionary", "Tuple", "Set"], 2),
            ("What does Django's ORM help you do?", ["Query databases with Python", "Design icons", "Compile CSS", "Host DNS"], 0),
            ("Which HTTP status means a resource was created?", ["200", "201", "401", "500"], 1),
            ("What does a DRF serializer do?", ["Only route URLs", "Only send emails", "Validate and transform data", "Encrypt every request"], 2),
            ("Which response usually indicates missing or invalid token authentication?", ["201", "204", "404", "401"], 3),
        ]
        for text, choices, correct in examples:
            data["questions"].append({"text": text, "choices": [
                {"text": choice, "is_correct": index == correct} for index, choice in enumerate(choices)]})
        serializer = QuizWriteSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(owner=owner)
        self.stdout.write(self.style.SUCCESS("Sample quiz created."))
