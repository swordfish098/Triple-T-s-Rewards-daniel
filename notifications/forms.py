# notifications/forms.py
from flask_wtf import FlaskForm
# Combined imports
from wtforms import BooleanField, SelectMultipleField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length
from models import User, Role # Added Role import
from extensions import db # Added db import

# Form for sending notifications
class SendNotificationForm(FlaskForm):
    # Use SelectMultipleField for potentially multiple recipients
    recipients = SelectMultipleField("Recipients", coerce=int)

    # Keep the message field with added Length validation from HEAD
    message = TextAreaField('Message Content',
                            validators=[
                                DataRequired(),
                                Length(min=5, max=500, message='Message must be between 5 and 500 characters.')
                            ],
                            render_kw={"rows": 5}) # Keep render_kw for better UI

    # Keep SubmitField
    submit = SubmitField('Send Message')
    # Keep send_all field
    send_all = BooleanField('Send to All Drivers')

    def __init__(self, current_user_code=None, *args, **kwargs):
        super(SendNotificationForm, self).__init__(*args, **kwargs)

        # Use the more detailed query from the 078d... version
        rows = (User.query
                .with_entities(
                    User.USER_CODE,   # index 0
                    User.USERNAME,    # index 1
                    User.FNAME,       # index 2
                    User.LNAME        # index 3
                )
                .filter(User.IS_ACTIVE == 1) # Filter for active users
                .order_by(User.USERNAME.asc())
                .all())

        # Exclude the current user sending the message
        if current_user_code is not None:
            # Ensure comparison is done with the correct type (int)
            rows = [r for r in rows if r[0] != int(current_user_code)]

        # Set the choices for the recipients field (plural) using the format from 078d...
        self.recipients.choices = [
            (user_code, f"{username} ({(fname or '').strip()} {(lname or '').strip()})".strip())
            for (user_code, username, fname, lname) in rows
        ]