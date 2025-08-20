from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from auth import login_required, create_user, authenticate_user
from models import Ingredient, Meal, IngredientUsage, MealNutrition, SavedRecipe, DailyAdvice, db
from datetime import datetime, timedelta
import json
from utils import calculate_meal_nutrition, get_meals_for_date, get_daily_nutrition_history, get_user_favorite_meal, get_ingredient_cloud_data
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


# Create blueprint for page views
views_bp = Blueprint('views', __name__)

limiter = Limiter(
    get_remote_address,
    default_limits=["10 per minute"]
)


@limiter.limit("1 per minute")
@views_bp.route('/')
def index():
    """Home page"""
    if 'user_id' in session:
        return redirect(url_for('views.chat'))
    return render_template('login.html')

@views_bp.route('/chat')
@login_required
def chat():
    """New conversational chat interface"""
    return render_template('chat.html')


@limiter.limit("1 per minute")
@views_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and authentication"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        print(f"Login attempt for username: {username}, {password}")
        if not username or not password:
            flash('Please provide both username and password.', 'error')
            return render_template('login.html')
        
        user = authenticate_user(username, password)
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login successful!', 'success')
            print("Redirecting to chat...")
            return redirect(url_for('views.chat'))
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('login.html')


@limiter.limit("1 per minute")
@views_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """Signup page and user registration"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        if not all([username, email, password, confirm_password]):
            flash('Please fill in all fields.', 'error')
            return render_template('signup.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('signup.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('signup.html')
        
        try:
            # Check if user already exists
            from auth import get_user_by_username, get_user_by_email
            
            if get_user_by_username(username):
                flash('Username already exists.', 'error')
                return render_template('signup.html')
            
            if get_user_by_email(email):
                flash('Email already registered.', 'error')
                return render_template('signup.html')
            
            # Create new user
            user = create_user(username, email, password)
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('views.login'))
            
        except Exception as e:
            flash(f'Error creating account: {str(e)}', 'error')
            return render_template('signup.html')
    
    return render_template('signup.html')


@views_bp.route('/dashboard', methods=['GET', 'POST'])
@limiter.limit("1 per minute")
@login_required
def dashboard():
    """Main dashboard interface page"""
    if request.method == 'POST':
        date_str = request.form.get('date')
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.now().date()
        except Exception:
            selected_date = datetime.now().date()
    else:
        selected_date = datetime.now().date()

    meals_grouped = get_meals_for_date(selected_date, session['user_id'])
    start_date = selected_date - timedelta(days=29)
    history = get_daily_nutrition_history(session['user_id'], start_date, selected_date)
    favorite_meal = get_user_favorite_meal(session['user_id'])
    ingredient_cloud = get_ingredient_cloud_data(session['user_id'], start_date, selected_date)
    # Tip of the Day: load existing
    today_advice = None
    try:
        row = DailyAdvice.query.filter_by(user_id=session['user_id'], date=selected_date).first()
        if row:
            today_advice = row.advice
    except Exception:
        today_advice = None
    return render_template('dashboard.html', meals=meals_grouped, history=history, selected_date=selected_date, favorite_meal=favorite_meal, ingredient_cloud=ingredient_cloud, today_advice=today_advice)


@views_bp.route('/recipes')
@limiter.limit("1 per minute")
@login_required
def recipes():
    """Saved recipes page"""
    rows = SavedRecipe.query.filter_by(user_id=session['user_id']).order_by(SavedRecipe.created_at.desc()).all()
    return render_template('recipes.html', recipes=rows)

@limiter.limit("1 per minute")
@views_bp.route('/add_meal', methods=['GET', 'POST'])
def add_meal():
    """Add a meal"""
    if request.method == 'POST':
        date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        name = request.form.get('name')
        raw_ingredients = request.form.getlist('ingredient_name[]')
        raw_weights = request.form.getlist('ingredient_weight[]')

        # Normalize ids and weights
        ingredient_ids = []
        ingredient_weights = []
        for ing, wt in zip(raw_ingredients, raw_weights):
            try:
                ingredient_ids.append(int(ing))
            except Exception:
                continue
            try:
                ingredient_weights.append(float(wt))
            except Exception:
                ingredient_weights.append(0.0)

        # Update ingredient usage (single commit later)
        for ing_id, grams in zip(ingredient_ids, ingredient_weights):
            usage = IngredientUsage.query.filter_by(ingredient_id=ing_id, user_id=session['user_id']).first()
            if usage:
                usage.quantity += float(grams)
            else:
                db.session.add(IngredientUsage(ingredient_id=ing_id, user_id=session['user_id'], quantity=float(grams)))

        meal_type = request.form.get('meal_type')
        ingredients_list = []
        for ing_id, grams in zip(ingredient_ids, ingredient_weights):
            ingredients_list.append({'ingredient_id': int(ing_id), 'weight': float(grams)})

        # Store structured JSON, not stringified JSON
        meal = Meal(name=name, ingredients=ingredients_list, meal_type=meal_type, user_id=session['user_id'], date=date)
        db.session.add(meal)
        db.session.flush()

        calories, protein, carbs, fat = calculate_meal_nutrition(ingredient_ids, ingredient_weights)
        meal_nutrition = MealNutrition(meal_id=meal.id, calories=calories, protein=protein, carbs=carbs, fat=fat)
        db.session.add(meal_nutrition)

        db.session.commit()
        print(f"Adding meal: {meal}")
        
        return redirect(url_for('views.dashboard'))
    else:
        ingredients = Ingredient.query.all()
        return render_template('add_meal.html', ingredients=ingredients)

@limiter.limit("1 per minute")
@views_bp.route('/logout')
def logout():
    """Logout user and clear session"""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('views.index')) 