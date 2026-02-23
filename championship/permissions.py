from django.core.exceptions import PermissionDenied

def admin_only(view_func):
    def wrap(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role == 'ADMIN':
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return wrap