from rest_framework.permissions import BasePermission

class IsBoardOfDirectors(BasePermission):
    """
    Allows access only to users with access_level = -1.
    """
    def has_permission(self, request, view):
        # Check if the user is authenticated and has access_level = -1
        return request.user and request.user.is_authenticated and request.user.access_level == -1