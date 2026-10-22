from copy import deepcopy
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase
from .models import Attempt, Quiz
from .serializers import QuizWriteSerializer

class QuizAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.author = User.objects.create_user("author", password="A-test-password-472!")
        cls.other_author = User.objects.create_user("other_author", password="A-test-password-472!")
        cls.learner = User.objects.create_user("learner", password="A-test-password-472!")
        cls.other = User.objects.create_user("other", password="A-test-password-472!")
        group = Group.objects.create(name="Instructors")
        cls.author.groups.add(group)
        cls.other_author.groups.add(group)
        cls.payload = {"title": "Django basics", "category": "Development", "is_published": True,
                       "questions": [
                           {"text": "What is DRF?", "choices": [
                               {"text": "Django REST Framework", "is_correct": True},
                               {"text": "A database", "is_correct": False}]},
                           {"text": "Which status means created?", "choices": [
                               {"text": "201", "is_correct": True},
                               {"text": "404", "is_correct": False}]}]}
        serializer = QuizWriteSerializer(data=deepcopy(cls.payload))
        serializer.is_valid(raise_exception=True)
        cls.quiz = serializer.save(owner=cls.author)
        draft = deepcopy(cls.payload)
        draft["is_published"] = False
        serializer = QuizWriteSerializer(data=draft)
        serializer.is_valid(raise_exception=True)
        cls.draft = serializer.save(owner=cls.author)

    def setUp(self):
        cache.clear()

    def login_as(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def answers(self, quiz=None):
        quiz = quiz or self.quiz
        return [{"question_id": q.id, "choice_id": q.choices.get(is_correct=True).id} for q in quiz.questions.all()]

    def submit(self, answers=None, quiz=None, **extras):
        quiz = quiz or self.quiz
        return self.client.post(reverse("quiz-submit", args=[quiz.id]),
                                {"answers": self.answers(quiz) if answers is None else answers, **extras}, format="json")

    def test_registration_hashes_password_and_cannot_grant_roles(self):
        response = self.client.post(reverse("register"), {
            "username": "newlearner", "email": "learner@example.com", "password": "A-unique-password-578!",
            "role": "admin", "is_staff": True, "is_superuser": True, "groups": ["Instructors"]}, format="json")
        self.assertEqual(response.status_code, 201)
        user = get_user_model().objects.get(username="newlearner")
        self.assertTrue(user.check_password("A-unique-password-578!"))
        self.assertFalse(user.is_staff or user.is_superuser or user.groups.exists())
        self.assertEqual(response.data["user"]["role"], "learner")
        self.assertNotIn("password", response.data["user"])

    def test_registration_rejects_weak_password_and_duplicate_username(self):
        for username, password in [("fresh", "123"), ("learner", "A-unique-password-578!")]:
            response = self.client.post(reverse("register"), {"username": username, "email": "a@example.com",
                                                                "password": password}, format="json")
            self.assertEqual(response.status_code, 400)

    def test_login_me_and_logout_revoke_token(self):
        response = self.client.post(reverse("login"), {"username": "learner", "password": "A-test-password-472!"})
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + response.data["token"])
        self.assertEqual(self.client.get(reverse("me")).data["username"], "learner")
        self.assertEqual(self.client.post(reverse("logout")).status_code, 204)
        self.assertEqual(self.client.get(reverse("me")).status_code, 401)

    def test_bad_credentials_and_inactive_user_cannot_login(self):
        for username, password in [("learner", "wrong"), ("missing", "wrong")]:
            self.assertEqual(self.client.post(reverse("login"), {"username": username, "password": password}).status_code, 401)
        self.learner.is_active = False
        self.learner.save()
        self.assertEqual(self.client.post(reverse("login"), {"username": "learner", "password": "A-test-password-472!"}).status_code, 401)

    def test_anonymous_cannot_read_quizzes_submit_or_access_history(self):
        for path in [reverse("quiz-list"), reverse("attempt-list"), reverse("quiz-detail", args=[self.quiz.id])]:
            self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.submit().status_code, 401)

    def test_learner_cannot_create_quiz(self):
        self.login_as(self.learner)
        self.assertEqual(self.client.post(reverse("quiz-list"), self.payload, format="json").status_code, 403)

    def test_instructor_can_create_draft_then_publish(self):
        self.login_as(self.author)
        data = deepcopy(self.payload)
        data["is_published"] = False
        data["owner"] = self.other.id
        response = self.client.post(reverse("quiz-list"), data, format="json")
        self.assertEqual(response.status_code, 201)
        quiz = Quiz.objects.get(pk=response.data["id"])
        self.assertEqual(quiz.owner_id, self.author.id)
        response = self.client.patch(reverse("quiz-detail", args=[quiz.id]), {"is_published": True}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_published"])

    def test_drafts_are_private(self):
        self.login_as(self.learner)
        self.assertEqual(self.client.get(reverse("quiz-detail", args=[self.draft.id])).status_code, 404)
        ids = [q["id"] for q in self.client.get(reverse("quiz-list")).data["results"]]
        self.assertNotIn(self.draft.id, ids)

    def test_other_instructor_cannot_edit_or_delete_quiz(self):
        self.login_as(self.other_author)
        detail = reverse("quiz-detail", args=[self.quiz.id])
        self.assertEqual(self.client.patch(detail, {"title": "Changed"}).status_code, 403)
        self.assertEqual(self.client.delete(detail).status_code, 403)
        self.assertEqual(self.client.get(reverse("quiz-detail", args=[self.draft.id])).status_code, 404)

    def test_author_can_edit_replace_questions_and_delete_draft(self):
        self.login_as(self.author)
        path = reverse("quiz-detail", args=[self.draft.id])
        self.assertEqual(self.client.patch(path, {"title": "Edited"}).status_code, 200)
        data = deepcopy(self.payload)
        data["is_published"] = False
        data["questions"] = data["questions"][:1]
        self.assertEqual(self.client.put(path, data, format="json").status_code, 200)
        self.assertEqual(self.draft.questions.count(), 1)
        self.assertEqual(self.client.delete(path).status_code, 204)

    def test_staff_can_manage_other_authors_drafts(self):
        self.other.is_staff = True
        self.other.save()
        self.login_as(self.other)
        self.assertEqual(self.client.patch(reverse("quiz-detail", args=[self.draft.id]), {"title": "Staff edit"}).status_code, 200)

    def test_answer_key_is_not_exposed_to_learners_or_other_instructors(self):
        for user in [self.learner, self.other_author]:
            self.login_as(user)
            detail = self.client.get(reverse("quiz-detail", args=[self.quiz.id]))
            listing = self.client.get(reverse("quiz-list"))
            self.assertNotIn("is_correct", str(detail.data))
            self.assertNotIn("is_correct", str(listing.data))
        self.login_as(self.author)
        self.assertIn("is_correct", str(self.client.get(reverse("quiz-detail", args=[self.quiz.id])).data))

    def test_published_quiz_cannot_be_changed_unpublished_or_deleted(self):
        self.login_as(self.author)
        path = reverse("quiz-detail", args=[self.quiz.id])
        for payload in [{"title": "Changed"}, {"is_published": False}, {"questions": []}]:
            self.assertEqual(self.client.patch(path, payload, format="json").status_code, 400)
        self.assertEqual(self.client.delete(path).status_code, 400)

    def test_invalid_questions_rejected_atomically(self):
        self.login_as(self.author)
        invalid_sets = [[], [{"text": "Q", "choices": [{"text": "A", "is_correct": True}]}],
                        [{"text": "Q", "choices": [{"text": "A", "is_correct": True}, {"text": "B", "is_correct": True}]}],
                        [{"text": "Q", "choices": [{"text": "A", "is_correct": False}, {"text": "B", "is_correct": False}]}],
                        [{"text": "Q", "choices": [{"text": "Same", "is_correct": True}, {"text": "same", "is_correct": False}]}]]
        count = Quiz.objects.count()
        for questions in invalid_sets:
            data = {**self.payload, "questions": questions}
            self.assertEqual(self.client.post(reverse("quiz-list"), data, format="json").status_code, 400)
        self.assertEqual(Quiz.objects.count(), count)

    def test_grading_is_server_side_and_retakes_are_allowed(self):
        self.login_as(self.learner)
        answers = self.answers()
        first = self.quiz.questions.first()
        answers[0]["choice_id"] = first.choices.get(is_correct=False).id
        response = self.submit(answers, score=999, user=self.other.id)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["score"], 1)
        self.assertEqual(response.data["total"], 2)
        self.assertEqual(response.data["percentage"], 50.0)
        self.assertEqual(Attempt.objects.get(pk=response.data["id"]).user_id, self.learner.id)
        self.assertEqual(response.data["review"][0]["correct_answer"], "Django REST Framework")
        self.assertEqual(self.submit().data["score"], 2)
        self.assertEqual(Attempt.objects.filter(user=self.learner).count(), 2)

    def test_invalid_submissions_do_not_create_attempts(self):
        self.login_as(self.learner)
        valid = self.answers()
        invalid = [[], valid[:1], [valid[0], valid[0]], self.answers(self.draft),
                   [{"question_id": valid[0]["question_id"], "choice_id": valid[1]["choice_id"]}, valid[1]]]
        for answers in invalid:
            self.assertEqual(self.submit(answers).status_code, 400)
        self.assertEqual(Attempt.objects.count(), 0)

    def test_draft_cannot_be_submitted_even_by_owner(self):
        self.login_as(self.author)
        self.assertEqual(self.submit(quiz=self.draft).status_code, 400)

    def test_attempt_history_is_private_even_from_instructors(self):
        self.login_as(self.learner)
        result = self.submit().data
        self.assertEqual(self.client.get(reverse("attempt-list")).data["count"], 1)
        for user in [self.other, self.author]:
            self.login_as(user)
            self.assertEqual(self.client.get(reverse("attempt-list")).data["count"], 0)
            self.assertEqual(self.client.get(reverse("attempt-detail", args=[result["id"]])).status_code, 404)

    def test_search_and_mine_filters(self):
        self.login_as(self.author)
        self.assertEqual(self.client.get(reverse("quiz-list"), {"search": "missing"}).data["count"], 0)
        self.assertEqual(self.client.get(reverse("quiz-list"), {"mine": "true"}).data["count"], 2)
        self.login_as(self.learner)
        self.assertEqual(self.client.get(reverse("quiz-list"), {"mine": "true"}).data["count"], 0)

    def test_archived_quiz_is_unavailable_but_previous_result_is_preserved(self):
        self.login_as(self.learner)
        result = self.submit().data
        self.quiz.is_archived = True
        self.quiz.save(update_fields=["is_archived"])
        self.assertEqual(self.client.get(reverse("quiz-detail", args=[self.quiz.id])).status_code, 404)
        self.assertEqual(self.submit().status_code, 404)
        history = self.client.get(reverse("attempt-detail", args=[result["id"]]))
        self.assertEqual(history.status_code, 200)
        self.assertFalse(history.data["quiz_available"])
        self.assertEqual(history.data["score"], 2)
        for user in [self.learner, self.author]:
            self.login_as(user)
            ids = [q["id"] for q in self.client.get(reverse("quiz-list")).data["results"]]
            self.assertNotIn(self.quiz.id, ids)

    def test_auth_endpoint_is_throttled(self):
        for _ in range(20):
            self.client.post(reverse("login"), {"username": "missing", "password": "wrong"})
        self.assertEqual(self.client.post(reverse("login"), {"username": "missing", "password": "wrong"}).status_code, 429)

    def test_homepage_and_api_root_load(self):
        self.assertContains(self.client.get("/"), "Quizcraft")
        self.login_as(self.learner)
        self.assertEqual(self.client.get("/api/").status_code, 200)
