from flask_wtf import FlaskForm
from wtforms import TextAreaField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length
from models import User

# Assuming your User model has USERNAME, FNAME, and LNAME attributes
class SendNotificationForm(FlaskForm):
    recipient = SelectField('Recipient', 
                            validators=[DataRequired()], 
                            coerce=int)
    
    message = TextAreaField('Message Content', 
                            validators=[
                                DataRequired(), 
                                Length(min=5, max=500, message='Message must be between 5 and 500 characters.')
                            ], 
                            render_kw={"rows": 5})
    
    submit = SubmitField('Send Message')
    
    def __init__(self, current_user_code=None, *args, **kwargs):
        super(SendNotificationForm, self).__init__(*args, **kwargs)
        
        # 1. Fetch all active users, ordered by Username
        users = User.query.filter_by(IS_ACTIVE=True).order_by(User.USERNAME).all()
        
        choices = []
        for u in users:
            # 2. Create the display label: "USERNAME (First Name Last Name)"
            display_name = f"{u.USERNAME} ({u.FNAME} {u.LNAME})"
            
            # 3. Skip the current user if their USER_CODE is provided
            if current_user_code is None or u.USER_CODE != current_user_code:
                # The value (u.USER_CODE) must be the integer ID you save in the database
                choices.append((u.USER_CODE, display_name))
        
        # 4. Set the final choices list
        self.recipient.choices = choices