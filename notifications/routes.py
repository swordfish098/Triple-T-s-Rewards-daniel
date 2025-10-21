# notifications/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
# Removed redundant imports
from common.decorators import role_required
# Removed unused logging import
from datetime import datetime
# Removed redundant sqlalchemy import
# Combined model imports
from models import User, Role, Notification, db # Removed unused models
# Removed redundant db import
from .forms import SendNotificationForm

# Blueprint for notification-related routes
notification_bp = Blueprint('notification_bp', __name__, template_folder="../templates")

@notification_bp.route('/notifications')
@login_required
def notifications():
    """Displays the user's notifications and marks unread ones as read."""
    # Use the more efficient query and update logic from 078d...
    notifs = (
        Notification.query
        .filter_by(RECIPIENT_CODE=current_user.USER_CODE) # Filter by primary key
        .order_by(Notification.READ_STATUS.asc(), Notification.TIMESTAMP.desc())
        .limit(50) # Limit results for performance
        .all()
    )

    # Mark unread as read using a bulk update for efficiency
    updated_count = (
        Notification.query
        .filter_by(RECIPIENT_CODE=current_user.USER_CODE, READ_STATUS=False)
        .update({Notification.READ_STATUS: True}, synchronize_session=False) # Use synchronize_session=False for bulk update
    )
    if updated_count: # Only commit if something was updated
        db.session.commit()

    return render_template('notifications/list.html', notifications=notifs)

# Route for sending messages, adapted from 078d... to use the combined form
@notification_bp.route('/message/send', methods=['GET', 'POST'])
@login_required
# Add role requirement: only sponsors and admins can send
@role_required(Role.SPONSOR, Role.ADMINISTRATOR)
def send_message():
    """Handles sending notifications to users."""
    # Initialize the form, passing the current user's code to exclude them
    form = SendNotificationForm(current_user_code=current_user.USER_CODE)

    if form.validate_on_submit():
        message_content = form.message.data
        send_all_drivers = form.send_all.data # Use form data for send_all
        selected_ids = form.recipients.data # Use form data for selected recipients

        # Determine target recipients
        recipient_query = User.query.filter(
            User.IS_ACTIVE == 1,
            User.USER_CODE != current_user.USER_CODE # Exclude self
        ).with_entities(User.USER_CODE, User.USERNAME)

        if send_all_drivers:
            # If sending to all drivers, filter by role
            recipients = recipient_query.filter(User.USER_TYPE == Role.DRIVER).all()
            recipient_description = "all active drivers"
        else:
            if not selected_ids:
                flash("Please select at least one recipient or check 'Send to All Drivers'.", "warning")
                # Re-render form with validation errors if possible, or redirect
                return render_template('notifications/send_message.html', form=form)

            # Filter by the selected user codes
            recipients = recipient_query.filter(User.USER_CODE.in_(selected_ids)).all()
            recipient_description = f"{len(recipients)} selected user(s)"

        if not recipients:
            flash("No valid recipients found for your selection.", "warning")
            return render_template('notifications/send_message.html', form=form)

        # Create Notification objects in bulk
        notifications_to_send = [
            Notification(
                RECIPIENT_CODE=user_code,
                SENDER_CODE=current_user.USER_CODE,
                MESSAGE=message_content,
                READ_STATUS=False, # Notifications start as unread (False or 0)
                TIMESTAMP=datetime.utcnow(),
            )
            for (user_code, _username) in recipients
        ]

        try:
            db.session.add_all(notifications_to_send)
            db.session.commit()
            flash(f"Message successfully sent to {recipient_description}!", 'success')
            return redirect(url_for('notification_bp.notifications'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error sending messages: {e}', 'danger')

    # For GET request or if form validation fails
    return render_template('notifications/send_message.html', form=form)


@notification_bp.route('/notifications/unread_count', methods=['GET'])
@login_required
def get_unread_count():
    """API endpoint to get the count of unread notifications."""
    if not current_user.is_authenticated:
        # Should not happen due to @login_required, but good practice
        return jsonify({'count': 0}), 401

    count = Notification.query.filter_by(
        RECIPIENT_CODE=current_user.USER_CODE,
        READ_STATUS=False # Assuming False means unread
    ).count()
    return jsonify({'count': count})