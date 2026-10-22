from django.conf import settings
from django.db import models

class Quiz(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="quizzes")
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True, max_length=2000)
    category = models.CharField(max_length=60, default="General")
    is_published = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title

class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    text = models.CharField(max_length=1000)
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ["position", "id"]
        constraints = [models.UniqueConstraint(fields=["quiz", "position"], name="unique_question_position")]

class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]

class Attempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attempts")
    quiz = models.ForeignKey(Quiz, on_delete=models.PROTECT, related_name="attempts")
    score = models.PositiveIntegerField()
    total = models.PositiveIntegerField()
    # Snapshot preserves the submitted answer and grading details in attempt history.
    review = models.JSONField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at", "-id"]
        constraints = [models.CheckConstraint(condition=models.Q(score__lte=models.F("total")), name="score_within_total")]
