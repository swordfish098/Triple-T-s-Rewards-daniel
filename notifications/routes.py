from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from common.decorators import role_required
from common.logging import log_audit_event, LOGIN_EVENT
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from models import User, Role, StoreSettings, db, DriverApplication, Sponsor, Notification
from extensions import db
from datetime import datetime
from .forms import SendNotificationForm

# Blueprint for notification-related routes
notification_bp = Blueprint('notification_bp', __name__, template_folder="../templates")

@notification_bp.route('/notifications')
@login_required
def notifications():
    notifications = Notification.query.filter_by(
        recipient=current_user
    ).order_by(Notification.READ_STATUS.asc(), Notification.TIMESTAMP.desc()).limit(50).all()
    
    unread_to_mark = Notification.query.filter_by(
        recipient=current_user,
        READ_STATUS=False
    ).all()
    
    for notif in unread_to_mark:
        notif.READ_STATUS = True
        
    db.session.commit()
    
    return render_template('notifications/list.html', notifications=notifications)

# In your notifications Blueprint file (e.g., notify_bp.py)

# In your notifications Blueprint file (e.g., notify_bp.py)

@notification_bp.route('/message/send', methods=['GET', 'POST'])
@login_required
def send_message():
    form = SendNotificationForm(current_user_code=current_user.USER_CODE)

    if form.validate_on_submit():
        recipient_code = form.recipient.data
        message_content = form.message.data
        sender_code = current_user.USER_CODE
        
        # --- FIX STARTS HERE ---
        
        # 1. Convert the list of choices (tuples) into a dictionary {value: label}
        choices_dict = dict(form.recipient.choices)
        
        # 2. Safely retrieve the full display name using the submitted ID
        recipient_name = choices_dict.get(recipient_code, f"User ID {recipient_code}") 
        
        # --- FIX ENDS HERE ---

        try:
            Notification.create_notification(
                recipient_code=recipient_code,
                sender_code=sender_code,
                message=message_content
            )
            
            # Use the correctly retrieved name in the flash message
            flash(f'Message successfully sent to {recipient_name}!', 'success')
            return redirect(url_for('notification_bp.notifications'))
            
        except Exception as e:
            flash(f'Error sending message: {e}', 'danger')
            
    return render_template('notifications/send_message.html', form=form)
            
    return render_template('notifications/send_message.html', form=form)

@notification_bp.route('/notifications/unread_count', methods=['GET'])
@login_required
def get_unread_count():
    # Ensure current_user.USER_CODE is the primary key for the recipient filter
    if not current_user.is_authenticated:
        return jsonify({'count': 0})
        
    count = Notification.query.filter_by(
        RECIPIENT_CODE=current_user.USER_CODE,
        READ_STATUS=False
    ).count()
    return jsonify({'count': count})