from flask import Flask, render_template , jsonify
from flask import request, session, redirect, render_template, flash
from auth.auth_client import create_supabase_client
from sqlalchemy import create_engine
from flask_sqlalchemy import SQLAlchemy
from config import Config
from model import db,User, UserProfile, EmergencyContact, LanguagePreference, Pod, PodMember,PodItinerary, PodPacking, PodBudget

import random
import string
from agent.itnerary import generate_itinerary_from_prompt
from agent.i_update import refine_itinerary
from agent.packing import generate_packing_list
from agent.budget import generate_budget_plan
from agent.destination_plan import research_reply

from functools import wraps
from flask import make_response
from dotenv import load_dotenv
import os


app = Flask(__name__)
supabase = create_supabase_client()
load_dotenv()

app.secret_key = os.getenv("FLASK_SECRET_KEY")


def nocache(view):
    @wraps(view)
    def no_cache(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    return no_cache

# Create the SQLAlchemy engine manually with SSL
app.config["SQLALCHEMY_DATABASE_URI"] = Config.DB_URI
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = Config.ENGINE_OPTIONS
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()



@app.route('/')
def home():
    if 'user' in session:
        return redirect('/dashboard')
    return render_template('home.html')




@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        res = supabase.auth.sign_in_with_password({"email": email, "password": password})

        if res.user:
            session['user'] = {
                "id": res.user.id,
                "email": res.user.email
            }
            session['access_token'] = res.session.access_token
            return redirect('/dashboard')
        else:
            flash("Invalid credentials")
    return render_template("login.html")

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        res = supabase.auth.sign_up({
            "email": email,
            "password": password
        })

        if res.user:
            # Store Supabase user info temporarily in session
            session['user'] = {
                "id": res.user.id,
                "email": res.user.email
            }
            session['access_token'] = res.session.access_token
            existing_user = User.query.get(res.user.id)
            if not existing_user:
                new_user = User(id=res.user.id, email=res.user.email)
                db.session.add(new_user)
                db.session.commit()
            

            # Redirect to user info form
            return redirect('/profile')
        else:
            flash("Signup failed.")
    return render_template("sign_up.html")

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')

    user_id = session['user']['id']
    pods = db.session.query(Pod).join(PodMember).filter(PodMember.user_id == user_id).all()
    return render_template('dashboard.html', pods=pods)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' not in session:
        return redirect('/login')

    user_id = session['user']['id']

    if request.method == 'POST':
        name = request.form['name']
        blood = request.form['blood_group']
        health = request.form['health_conditions']
        allergies = request.form['allergies']
        food = request.form['food_preferences']
        travel = request.form['travel_preferences']
        e_name = request.form['emergency_name']
        e_relation = request.form['emergency_relation']
        e_phone = request.form['emergency_phone']
        e_email = request.form['emergency_email']
        lang = request.form['language']

        # --- Update User Name ---
        user = User.query.get(user_id)
        if user:
            user.name = name

        # --- Update or Create UserProfile ---
        profile = UserProfile.query.filter_by(user_id=user_id).first()
        if profile:
            profile.blood_group = blood
            profile.health_conditions = health
            profile.allergies = allergies
            profile.food_preferences = food
            profile.travel_preferences = travel
        else:
            profile = UserProfile(
                user_id=user_id,
                blood_group=blood,
                health_conditions=health,
                allergies=allergies,
                food_preferences=food,
                travel_preferences=travel
            )
            db.session.add(profile)

        # --- Update or Create EmergencyContact ---
        emergency = EmergencyContact.query.filter_by(user_id=user_id).first()
        if emergency:
            emergency.name = e_name
            emergency.relation = e_relation
            emergency.phone = e_phone
            emergency.email = e_email
        else:
            emergency = EmergencyContact(
                user_id=user_id,
                name=e_name,
                relation=e_relation,
                phone=e_phone,
                email=e_email
            )
            db.session.add(emergency)

        # --- Update or Create LanguagePreference ---
        language = LanguagePreference.query.filter_by(user_id=user_id).first()
        if language:
            language.preferred_language = lang
        else:
            language = LanguagePreference(user_id=user_id, preferred_language=lang)
            db.session.add(language)

        db.session.commit()

        return redirect('/dashboard')

    return render_template('user_info.html')


@app.route('/display', methods=['GET', 'POST'])
def display():
    if 'user' not in session:
        return redirect('/login')

    user_id = session['user']['id']

    # GET method: fetch existing data to show
    user = User.query.get(user_id)
    profile = UserProfile.query.filter_by(user_id=user_id).first()
    emergency = EmergencyContact.query.filter_by(user_id=user_id).first()
    language = LanguagePreference.query.filter_by(user_id=user_id).first()

    return render_template('profile.html', user=user, profile=profile, emergency=emergency, language=language)

def generate_invite_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


@app.route('/create_pod', methods=['GET', 'POST'])
def create_pod():
    if 'user' not in session:
        return redirect('/login')

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        destination = request.form['destination']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        estimated_budget = request.form.get('estimated_budget') or 0
        preferred_transport = request.form['preferred_transport']
        tags = request.form['tags']
        invite_code = generate_invite_code()
        created_by = session['user']['id']

        pod = Pod(
            name=name,
            description=description,
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            estimated_budget=estimated_budget,
            preferred_transport=preferred_transport,
            tags=tags,
            invite_code=invite_code,
            created_by=created_by
        )
        db.session.add(pod)
        db.session.commit()

        # Add creator as admin
        member = PodMember(user_id=created_by, pod_id=pod.id, role='admin')
        db.session.add(member)
        db.session.commit()

        return redirect('/dashboard')

    return render_template('create_pod.html')


@app.route('/pod/<int:pod_id>')
def view_pod(pod_id):
    if 'user' not in session:
        return redirect('/login')

    pod = Pod.query.get_or_404(pod_id)

    pod_members = PodMember.query.filter_by(pod_id=pod_id).all()
    members = []

    for m in pod_members:
        user = User.query.get(m.user_id)
        if user:
            members.append(user)

    # Dummy logic for avatars
    extra_count = max(0, len(members) - 3)

    # Itinerary
    #itinerary = Itinerary.query.filter_by(pod_id=pod_id).order_by(Itinerary.day_number).all()

    # Expenses
    '''expenses = Expense.query.filter_by(pod_id=pod_id).all()
    user_id = session['user']['id']
    total_expense = sum(e.amount for e in expenses)
    user_expense = sum(e.amount for e in expenses if e.user_id == user_id)
    budget_progress = int((total_expense / pod.estimated_budget) * 100) if pod.estimated_budget else 0'''
    itinerary = PodItinerary.query.filter_by(pod_id=pod_id).first()
    packing= PodPacking.query.filter_by(pod_id=pod_id).first()
    budget= PodBudget.query.filter_by(pod_id=pod_id).first()
    return render_template(
        'pod.html',
        pod=pod,
        members=members,
        extra_count=extra_count,
        itinerary=itinerary, # type: ignore
        packing=packing,# type: ignore
        budget=budget # type: ignore
        #total_expense=total_expense,
        #user_expense=user_expense,
        #budget_progress=budget_progress
    )

@app.route('/user/<string:user_id>')
def view_profile(user_id):
    user = User.query.get_or_404(user_id)
    profile = UserProfile.query.filter_by(user_id=user_id).first()
    emergency = EmergencyContact.query.filter_by(user_id=user_id).first()
    language = LanguagePreference.query.filter_by(user_id=user_id).first()

    return render_template('profile.html', user=user, profile=profile, emergency=emergency, language=language)


@app.route('/join_pod', methods=['GET', 'POST'])
def join_pod():
    if 'user' not in session:
        return redirect('/login')

    user_id = session['user']['id']
    error = None

    if request.method == 'POST':
        invite_code = request.form.get('invite_code').strip()

        pod = Pod.query.filter_by(invite_code=invite_code).first()

        if not pod:
            error = "Invalid invite code."
        else:
            # Check if already a member
            existing = PodMember.query.filter_by(user_id=user_id, pod_id=pod.id).first()
            if existing:
                error = "You are already in this pod."
            else:
                new_member = PodMember(
                    user_id=user_id,
                    pod_id=pod.id,
                    role='member'
                )
                db.session.add(new_member)
                db.session.commit()
                return redirect(f'/pod/{pod.id}')

    return render_template('join_pod.html', error=error)


@app.route('/user-info')
def user_info():
    return render_template('user_info.html') # should be removed later


@app.route('/pod/<int:pod_id>/itinerary/create', methods=['POST'])
def generate_itinerary_create(pod_id):
    if 'user' not in session:
        return redirect('/login')

    pod = Pod.query.get_or_404(pod_id)
    description = pod.description or ''
    destination = pod.destination or ''
    from_date = pod.start_date.strftime("%d %b %Y") if pod.start_date else ''
    to_date = pod.end_date.strftime("%d %b %Y") if pod.end_date else ''

    # AI prompt
    prompt = f"Create a detailed day-by-day travel itinerary for a trip to {destination} from {from_date} to {to_date}. Trip summary: {description}"
    user_id = session['user']['id']
    # Call AI (you define this in itinerary.py)
    generated_itinerary = generate_itinerary_from_prompt(user_id,prompt)

    # Save or update
    existing = PodItinerary.query.filter_by(pod_id=pod_id).first()
    if existing:
        existing.description = generated_itinerary
    else:
        new = PodItinerary(pod_id=pod_id, description=generated_itinerary, created_by=session['user']['id'])
        db.session.add(new)

    db.session.commit()
    return redirect(f'/pod/{pod_id}')


@app.route('/pod/<int:pod_id>/itinerary/edit', methods=['GET', 'POST'])
def edit_itinerary(pod_id):
    if 'user' not in session:
        return redirect('/login')

    #pod = Pod.query.get_or_404(pod_id)

    # Fetch itinerary if it exists
    itinerary = PodItinerary.query.filter_by(pod_id=pod_id).first()

    if request.method == 'POST':
        updated_text = request.form.get('content')

        if itinerary:
            itinerary.description = updated_text
        else:
            itinerary = PodItinerary(
                pod_id=pod_id,
                description=updated_text,
                created_by=session['user']['id']
            )
            db.session.add(itinerary)

        db.session.commit()
        return redirect(f'/pod/{pod_id}')


@app.route('/pod/<int:pod_id>/itinerary/ai-edit', methods=['POST'])
def refine_itinerary_with_ai(pod_id):
    if 'user' not in session:
        return redirect('/login')

    prompt = request.form.get('edit_prompt')
    if not prompt:
        return redirect(f'/pod/{pod_id}')

    pod = Pod.query.get_or_404(pod_id)
    itinerary = PodItinerary.query.filter_by(pod_id=pod_id).first()

    if not itinerary:
        flash("No itinerary exists to refine. Please create one first.", "warning")
        return redirect(f'/pod/{pod_id}')

    updated_text = refine_itinerary(current_plan=itinerary.description, update_prompt=prompt)

    itinerary.description = updated_text
    db.session.commit()

    flash("Itinerary refined using AI!", "success")
    return redirect(f'/pod/{pod_id}')


@app.route('/pod/<int:pod_id>/packing/create', methods=['POST'])
def generate_packing_create(pod_id):
    if 'user' not in session:
        return redirect('/login')

    itinerary = PodItinerary.query.filter_by(pod_id=pod_id).first()
    if not itinerary:
        return "No itinerary found. Please create an itinerary first.", 400


    packing_text = generate_packing_list(session['user']['id'], itinerary.description)

    existing = PodPacking.query.filter_by(pod_id=pod_id).first()
    if existing:
        existing.description = packing_text
    else:
        new = PodPacking(pod_id=pod_id, description=packing_text, created_by=session['user']['id'])
        db.session.add(new)

    db.session.commit()
    return redirect(f'/pod/{pod_id}')


@app.route('/pod/<int:pod_id>/packing/manual', methods=['POST'])
def update_packing_manual(pod_id):
    if 'user' not in session:
        return redirect('/login')

    description = request.form['description']
    packing = PodPacking.query.filter_by(pod_id=pod_id).first()
    if packing:
        packing.description = description
    else:
        new = PodPacking(pod_id=pod_id, description=description, created_by=session['user']['id'])
        db.session.add(new)

    db.session.commit()
    return redirect(f'/pod/{pod_id}')


@app.route('/pod/<int:pod_id>/packing/ai-edit', methods=['POST'])
def update_packing_ai(pod_id):
    if 'user' not in session:
        return redirect('/login')

    prompt = request.form['edit_prompt']
    existing = PodPacking.query.filter_by(pod_id=pod_id).first()
    if not existing:
        return "No packing list found to refine.", 400

    updated_packing = generate_packing_list(session['user']['id'], f"{existing.description}\nUser edit: {prompt}")
    existing.description = updated_packing

    db.session.commit()
    return redirect(f'/pod/{pod_id}')


@app.route('/pod/<int:pod_id>/budget/create', methods=['POST'])
def generate_budget_create(pod_id):
    if 'user' not in session:
        return redirect('/login')

    pod = Pod.query.get_or_404(pod_id)
    description = pod.description or ''
    destination = pod.destination or ''
    from_date = pod.start_date.strftime("%d %b %Y") if pod.start_date else ''
    to_date = pod.end_date.strftime("%d %b %Y") if pod.end_date else ''
    pod_budget = pod.estimated_budget or 0
    pod

    # Prompt for LLM
    user_preference = f"Create a comprehensive travel budget plan for a trip to {destination} from {from_date} to {to_date} and budget of {pod_budget}. " 
    detail=description
    user_id = session['user']['id']

    # Call your LLM (function to define in `budget.py`)
    ai_budget = generate_budget_plan(user_id, user_preference, detail)

    existing = PodBudget.query.filter_by(pod_id=pod_id).first()
    if existing:
        existing.description = ai_budget
    else:
        new = PodBudget(pod_id=pod_id, description=ai_budget, created_by=user_id)
        db.session.add(new)

    db.session.commit()
    return redirect(f'/pod/{pod_id}')

@app.route('/pod/<int:pod_id>/budget/edit', methods=['POST'])
def edit_budget_manual(pod_id):
    if 'user' not in session:
        return redirect('/login')

    new_text = request.form['description']
    existing = PodBudget.query.filter_by(pod_id=pod_id).first()

    if existing:
        existing.description = new_text
    else:
        new = PodBudget(pod_id=pod_id, description=new_text, created_by=session['user']['id'])
        db.session.add(new)

    db.session.commit()
    return redirect(f'/pod/{pod_id}')

@app.route('/pod/<int:pod_id>/budget/ai-edit', methods=['POST'])
def edit_budget_with_ai(pod_id):
    if 'user' not in session:
        return redirect('/login')

    edit_prompt = request.form['edit_prompt']
    existing = PodBudget.query.filter_by(pod_id=pod_id).first()
    original = existing.description if existing else ''

    full_prompt = f"{original}\n\nUser wants to refine it: {edit_prompt}"
    from budget import refine_budget_plan
    new_budget = refine_budget_plan(session['user']['id'], full_prompt)

    if existing:
        existing.description = new_budget
    else:
        new = PodBudget(pod_id=pod_id, description=new_budget, created_by=session['user']['id'])
        db.session.add(new)

    db.session.commit()
    return redirect(f'/pod/{pod_id}')



@app.route('/pod/<int:pod_id>/ask', methods=['POST'])
def ask(pod_id):
    user_input = request.json.get("message")
    session_id = session.get("session_id")
    
    pod = Pod.query.get_or_404(pod_id)
    description = pod.description or ''
    destination = pod.destination or ''
    from_date = pod.start_date.strftime("%d %b %Y") if pod.start_date else ''
    to_date = pod.end_date.strftime("%d %b %Y") if pod.end_date else ''
    pod_budget = pod.estimated_budget or 0
    pod

    # Prompt for LLM
    
    detail=f"User is in {destination} from {from_date} to {to_date} with a budget of {pod_budget}. Trip summary: {description}"
    user_id = session['user']['id']

    if not user_input:
        return jsonify({"response": "Please ask something."})

    response_html = research_reply(user_id,detail)
    return jsonify({"response": response_html})

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')




if __name__ == '__main__':
    app.run(debug=True)
