from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from quizzes.models import Quiz
from quizzes.serializers import QuizWriteSerializer


QUESTIONS = [
    ("Which is a valid Python variable name?",
     ["2nd_score", "student-score", "student_score", "class"], 2),
    ("What is the value of 2 ** 3 + 1?",
     ["9", "7", "16", "6"], 0),
    ('What does "  hello  ".strip().upper() return?',
     ['"  HELLO  "', '"hello!"', '"HELLO WORLD"', '"HELLO"'], 3),
    ("After nums = [10, 20, 30] and nums.pop(), what is nums?",
     ["[20, 30]", "[10, 20]", "[10, 20, 30]", "[]"], 1),
    ('Given person = {"name": "Mira", "age": 22}, what does "name" in person evaluate to?',
     ["False, because membership checks values", '"Mira"', "True, because membership checks keys", "A TypeError is raised"], 2),
    ("What is the result of list(enumerate(['a', 'b'], start=1))?",
     ["[(1, 'a'), (2, 'b')]", "[(0, 'a'), (1, 'b')]", "[('a', 1), ('b', 2)]", "['a', 'b']"], 0),
    ("What does list(zip([1, 2, 3], ['a', 'b'])) produce?",
     ["[(1, 'a'), (2, 'b'), (3, None)]", "A ValueError is raised", "[(1, 2, 3), ('a', 'b')]", "[(1, 'a'), (2, 'b')]"], 3),
    ("Which statement about sorted(nums) is correct when nums is a list?",
     ["It sorts nums in place and returns None", "It returns a new sorted list and leaves nums unchanged", "It always returns a tuple", "It removes duplicates before sorting"], 1),
    ("What does {n: n * 2 for n in [1, 2, 3]} produce?",
     ["{1: 2, 2: 4, 3: 6}", "[2, 4, 6]", "{2: 1, 4: 2, 6: 3}", "{1, 2, 3}"], 0),
    ("What is the value of (lambda x, y=2: x * y)(4)?",
     ["6", "2", "8", "A TypeError is raised"], 2),
    ("For def profile(**kwargs): return kwargs, what does profile(name='Sam', level=2) return?",
     ["('Sam', 2)", "['name', 'level']", "('name', 'level')", "{'name': 'Sam', 'level': 2}"], 3),
    ("When does the else block of a try/except/else statement execute?",
     ["Only when an exception is caught", "When the try block finishes normally without an exception", "Before the try block", "Whenever the finally block raises an exception"], 1),
    ("Why is 'with open(...) as file:' useful for file handling?",
     ["It closes the file when the block exits, including when an exception occurs", "It reads the entire file into memory automatically", "It prevents every file-related exception", "It keeps the file open until Python exits"], 0),
    ("After gen = (n * 2 for n in range(3)), what do two consecutive next(gen) calls return?",
     ["0, then 0", "2, then 4", "0, then 2", "[0, 2, 4], then StopIteration"], 2),
    ("A child class defines its own instance method with the same name as a parent method. What happens when that method is called on a child instance?",
     ["The parent method always runs", "The child method runs through method overriding", "Both methods always run automatically", "Python raises a duplicate-method error"], 1),
]


class Command(BaseCommand):
    help = "Replace the previous Python quiz with a fresh 15-question practice quiz, preserving old results."

    @transaction.atomic
    def handle(self, *args, **options):
        owner, created = get_user_model().objects.get_or_create(
            username="quiz_demo_author", defaults={"is_active": False})
        if created:
            owner.set_unusable_password()
            owner.save()
        Quiz.objects.filter(owner=owner, title="Python: Basics to Intermediate").update(is_archived=True)
        title = "Python Practice: Core Concepts & Problem Solving"
        if Quiz.objects.filter(owner=owner, title=title).exists():
            self.stdout.write("Replacement Python quiz already exists.")
            return
        data = {
            "title": title,
            "description": "A fresh set of 15 basic-to-intermediate questions on Python expressions, strings, collections, iteration tools, functions, exception handling, files, generators, and classes.",
            "category": "Python",
            "is_published": True,
            "questions": [
                {"text": text, "choices": [
                    {"text": choice, "is_correct": index == correct}
                    for index, choice in enumerate(choices)]}
                for text, choices, correct in QUESTIONS
            ],
        }
        serializer = QuizWriteSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        quiz = serializer.save(owner=owner)
        self.stdout.write(self.style.SUCCESS(f"Published '{quiz.title}' with {quiz.questions.count()} questions (ID {quiz.pk})."))
