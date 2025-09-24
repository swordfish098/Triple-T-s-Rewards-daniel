# Triple-T's Rewards – Team 12

This repository contains the Flask scaffold for our CPSC-4910 senior project.  

Follow these steps to set up and run the project locally:

# Triple-T's Rewards – Team 12

This repository contains the **Flask scaffold** for our CPSC-4910 senior project.  
The goal is to build a rewards web application for the trucking industry, where drivers earn points for good driving behavior and redeem them with sponsor companies.

## 🚀 Quickstart (For Teammates)

Follow these steps to set up and run the project locally:

1. Clone the repo
  git clone git@github.com:<username>/Triple-T-s-Rewards-Team12.git
cd Triple-T-s-Rewards-Team12

2. Create and activate a virtual environment
   python3 -m venv venv
   source venv/bin/activate   # Mac/Linux
   venv\Scripts\activate      # Windows

3. Install dependencies
   pip install -r requirements.txt
   Run the app

4. Run the App
python app.py
Open your browser at http://127.0.0.1:5000
You’ll see the landing page with links to:

## EC2 Hosting
  1. Connect to Team12-EC2
  2. cd Triple-T's Rewards – Team 12
  3. git pull (keep updated)
  4. python3 -m venv venv #Create virtual environment
  5. source venv/bin/activate #activate virtual environment
  6. pip install -r requirements.txt
  7. pip install gunicorn # Python Web Server Gateway Interface 
  8. gunicorn --workers 3 --bind 0.0.0.0:8000 app:app #Launch application with gunicorn

Driver Dashboard (placeholder)

Sponsor Dashboard (placeholder)
