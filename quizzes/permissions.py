from rest_framework.permissions import BasePermission, SAFE_METHODS

def is_instructor(user):
    return user.is_authenticated and (user.is_staff or user.groups.filter(name="Instructors").exists())

class QuizPermissions(BasePermission):
    message = "Only instructors can create quizzes; only the owner or staff can change them."

    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.method in SAFE_METHODS or view.action == "submit" or is_instructor(request.user)
        )

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS or view.action == "submit":
            return obj.is_published or obj.owner_id == request.user.id or request.user.is_staff
        return request.user.is_staff or (is_instructor(request.user) and obj.owner_id == request.user.id)
