import functools
from flask import flash, redirect, url_for, g  # Import 'g'
from flask_login import current_user
from models import Role

def role_required(*roles, allow_admin=True, redirect_to=None):
    """
    Decorator to restrict access to routes based on user role.
    'roles' is a list of allowed role strings (e.g., Role.DRIVER).
    'allow_admin' (bool): If True, allows administrators to bypass role checks.
    'redirect_to' (str): The endpoint to redirect to if unauthorized.
    """
    
    def decorator(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("You must be logged in to view that page.", "info")
                return redirect(url_for(redirect_to or 'auth.login'))

            # 1. Admin bypass (if they are just being an admin)
            if (allow_admin and current_user.USER_TYPE == Role.ADMINISTRATOR):
                return view(*args, **kwargs)
                
            # 2. Impersonation bypass (if an admin is impersonating someone)
            #    We check g.impersonator, which is the *original* user (the admin).
            if getattr(g, 'is_impersonating', False) and g.impersonator and g.impersonator.USER_TYPE == Role.ADMINISTRATOR:
                return view(*args, **kwargs)

            # 3. Standard role check
            if current_user.USER_TYPE not in roles:
                flash("You do not have permission to view this page.", "danger")
                
                # Redirect to a role-appropriate dashboard
                if current_user.USER_TYPE == Role.ADMINISTRATOR:
                    return redirect(url_for('administrator_bp.dashboard'))
                elif current_user.USER_TYPE == Role.SPONSOR:
                    return redirect(url_for('sponsor_bp.dashboard'))
                elif current_user.USER_TYPE == Role.DRIVER:
                    return redirect(url_for('driver_bp.dashboard'))
                else:
                    # Fallback for unknown roles or errors
                    return redirect(url_for('common.index'))
            
            # If all checks pass
            return view(*args, **kwargs)
        return wrapped
    return decorator