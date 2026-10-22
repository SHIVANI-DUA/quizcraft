from django.contrib import admin
from .models import Attempt, Quiz

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "category", "is_published", "created_at"]
    list_filter = ["is_published", "category"]
    search_fields = ["title", "owner__username"]
    # Authoring uses the validated API to enforce nested question invariants.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ["user", "quiz", "score", "total", "submitted_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
