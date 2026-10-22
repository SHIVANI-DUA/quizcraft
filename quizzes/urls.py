from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (AttemptDetailView, AttemptListView, LoginView, LogoutView,
                    MeView, QuizViewSet, RegisterView)

router = DefaultRouter()
router.register("quizzes", QuizViewSet, basename="quiz")
urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("attempts/", AttemptListView.as_view(), name="attempt-list"),
    path("attempts/<int:pk>/", AttemptDetailView.as_view(), name="attempt-detail"),
    path("", include(router.urls)),
]
