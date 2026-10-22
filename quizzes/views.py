from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import Q
from rest_framework import generics, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from .models import Attempt, Quiz
from .permissions import QuizPermissions
from .serializers import (AttemptSerializer, QuizReadSerializer, QuizWriteSerializer,
                          RegisterSerializer, SubmissionSerializer, UserSerializer)

class AuthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

class RegisterView(AuthView):
    @transaction.atomic
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token = Token.objects.create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data}, status=status.HTTP_201_CREATED)

class LoginView(AuthView):
    def post(self, request):
        username, password = request.data.get("username"), request.data.get("password")
        if not isinstance(username, str) or not isinstance(password, str) or len(password) > 128:
            raise ValidationError("Provide a username and password.")
        user = authenticate(request=request, username=username, password=password)
        if user is None:
            return Response({"detail": "Invalid username or password."}, status=status.HTTP_401_UNAUTHORIZED)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data})

class LogoutView(APIView):
    def post(self, request):
        request.auth.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)

class QuizViewSet(viewsets.ModelViewSet):
    permission_classes = [QuizPermissions]
    search_fields = ["title", "description", "category"]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = Quiz.objects.filter(is_archived=False).select_related("owner").prefetch_related("questions__choices")
        if not self.request.user.is_staff:
            qs = qs.filter(Q(is_published=True) | Q(owner=self.request.user))
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category__iexact=category)
        if self.request.query_params.get("mine") == "true":
            qs = qs.filter(owner=self.request.user)
        return qs

    def get_serializer_class(self):
        return QuizWriteSerializer if self.action in ["create", "update", "partial_update"] else QuizReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quiz = serializer.save(owner=request.user)
        return Response(QuizReadSerializer(quiz, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        locked = Quiz.objects.select_for_update().get(pk=obj.pk)
        if locked.is_published:
            raise ValidationError("Published quizzes are immutable. Create a new quiz for revisions.")
        serializer = self.get_serializer(locked, data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        quiz = serializer.save()
        return Response(QuizReadSerializer(quiz, context={"request": request}).data)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        locked = Quiz.objects.select_for_update().get(pk=obj.pk)
        if locked.is_published:
            raise ValidationError("Published quizzes cannot be deleted.")
        locked.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def submit(self, request, pk=None):
        quiz = self.get_object()
        quiz = Quiz.objects.select_for_update().get(pk=quiz.pk)
        if quiz.is_archived or not quiz.is_published:
            raise ValidationError("You can only submit answers to a published quiz.")
        serializer = SubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        answers = serializer.validated_data["answers"]
        submitted = {a["question_id"]: a["choice_id"] for a in answers}
        questions = list(quiz.questions.prefetch_related("choices"))
        if len(submitted) != len(answers):
            raise ValidationError("Each question must appear exactly once.")
        if set(submitted) != {q.id for q in questions}:
            raise ValidationError("Answer every question in this quiz, and no questions from another quiz.")
        review, score = [], 0
        for question in questions:
            choices = list(question.choices.all())
            selected = next((c for c in choices if c.id == submitted[question.id]), None)
            if selected is None:
                raise ValidationError("A selected choice does not belong to its question.")
            correct = next(c for c in choices if c.is_correct)
            score += int(selected.is_correct)
            review.append({"question_id": question.id, "question": question.text,
                           "selected_choice_id": selected.id, "selected_answer": selected.text,
                           "correct_choice_id": correct.id, "correct_answer": correct.text,
                           "is_correct": selected.is_correct})
        attempt = Attempt.objects.create(user=request.user, quiz=quiz, score=score, total=len(questions), review=review)
        return Response(AttemptSerializer(attempt).data, status=status.HTTP_201_CREATED)

class AttemptListView(generics.ListAPIView):
    serializer_class = AttemptSerializer

    def get_queryset(self):
        return Attempt.objects.filter(user=self.request.user).select_related("quiz")

class AttemptDetailView(generics.RetrieveAPIView):
    serializer_class = AttemptSerializer

    def get_queryset(self):
        return Attempt.objects.filter(user=self.request.user).select_related("quiz")
