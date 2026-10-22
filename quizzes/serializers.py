from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from .models import Attempt, Choice, Question, Quiz
from .permissions import is_instructor

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "role"]

    def get_role(self, obj):
        return "admin" if obj.is_staff else "instructor" if is_instructor(obj) else "learner"

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def validate(self, attrs):
        try:
            validate_password(attrs["password"], User(username=attrs["username"], email=attrs["email"]))
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)

class ChoiceWriteSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=500)
    is_correct = serializers.BooleanField()

class QuestionWriteSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=1000)
    choices = ChoiceWriteSerializer(many=True, min_length=2, max_length=6)

    def validate_choices(self, choices):
        if sum(choice["is_correct"] for choice in choices) != 1:
            raise serializers.ValidationError("Each question needs exactly one correct choice.")
        if len({c["text"].casefold() for c in choices}) != len(choices):
            raise serializers.ValidationError("Choice texts must be distinct.")
        return choices

class QuizWriteSerializer(serializers.ModelSerializer):
    questions = QuestionWriteSerializer(many=True, min_length=1, max_length=50, required=True)

    class Meta:
        model = Quiz
        fields = ["id", "title", "description", "category", "is_published", "questions"]
        read_only_fields = ["id"]

    def _questions(self, quiz, questions):
        for position, data in enumerate(questions, start=1):
            choices = data.pop("choices")
            question = Question.objects.create(quiz=quiz, position=position, **data)
            Choice.objects.bulk_create([Choice(question=question, **choice) for choice in choices])

    @transaction.atomic
    def create(self, validated_data):
        questions = validated_data.pop("questions")
        quiz = Quiz.objects.create(**validated_data)
        self._questions(quiz, questions)
        return quiz

    @transaction.atomic
    def update(self, instance, validated_data):
        questions = validated_data.pop("questions", None)
        instance = super().update(instance, validated_data)
        if questions is not None:
            instance.questions.all().delete()
            self._questions(instance, questions)
        return instance

class ChoiceReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ["id", "text"]

class QuestionReadSerializer(serializers.ModelSerializer):
    choices = ChoiceReadSerializer(many=True)

    class Meta:
        model = Question
        fields = ["id", "text", "position", "choices"]

class QuizReadSerializer(serializers.ModelSerializer):
    owner = serializers.CharField(source="owner.username", read_only=True)
    question_count = serializers.SerializerMethodField()
    questions = QuestionReadSerializer(many=True, read_only=True)
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = Quiz
        fields = ["id", "title", "description", "category", "owner", "is_published",
                  "question_count", "can_edit", "created_at", "questions"]

    def get_question_count(self, obj):
        return len(obj.questions.all())

    def get_can_edit(self, obj):
        user = self.context["request"].user
        return not obj.is_published and (user.is_staff or (obj.owner_id == user.id and is_instructor(user)))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = self.context["request"].user
        if user.is_staff or instance.owner_id == user.id:
            for serialized, question in zip(data["questions"], instance.questions.all()):
                for item, choice in zip(serialized["choices"], question.choices.all()):
                    item["is_correct"] = choice.is_correct
        return data

class AnswerSerializer(serializers.Serializer):
    question_id = serializers.IntegerField(min_value=1)
    choice_id = serializers.IntegerField(min_value=1)

class SubmissionSerializer(serializers.Serializer):
    answers = AnswerSerializer(many=True, min_length=1, max_length=50)

class AttemptSerializer(serializers.ModelSerializer):
    quiz_title = serializers.CharField(source="quiz.title", read_only=True)
    quiz_available = serializers.SerializerMethodField()
    percentage = serializers.SerializerMethodField()

    class Meta:
        model = Attempt
        fields = ["id", "quiz", "quiz_title", "quiz_available", "score", "total", "percentage", "review", "submitted_at"]
        read_only_fields = fields

    def get_percentage(self, obj):
        return round(obj.score / obj.total * 100, 1) if obj.total else 0

    def get_quiz_available(self, obj):
        return obj.quiz.is_published and not obj.quiz.is_archived
