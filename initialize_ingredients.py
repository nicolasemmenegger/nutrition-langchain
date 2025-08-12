from models import Ingredient, db

def initialize_ingredients():
    """Initialize the ingredients table with default values (~50 common items)"""
    ingredients = [
        # Proteins
        {"name": "Egg", "calories": 78, "protein": 6.3, "carbs": 0.6, "fat": 5.3, "unit_weight": 50},
        {"name": "Chicken Breast", "calories": 165, "protein": 31.0, "carbs": 0.0, "fat": 3.6, "unit_weight": 100},
        {"name": "Salmon", "calories": 206, "protein": 22.0, "carbs": 0.0, "fat": 13.0, "unit_weight": 100},
        {"name": "Tuna (Canned in Water)", "calories": 132, "protein": 28.0, "carbs": 0.0, "fat": 1.3, "unit_weight": 100},
        {"name": "Tofu (Firm)", "calories": 144, "protein": 15.0, "carbs": 3.9, "fat": 8.0, "unit_weight": 150},
        {"name": "Lentils (Cooked)", "calories": 230, "protein": 18.0, "carbs": 40.0, "fat": 0.8, "unit_weight": 200},
        {"name": "Black Beans (Cooked)", "calories": 227, "protein": 15.2, "carbs": 40.4, "fat": 0.9, "unit_weight": 200},

        # Dairy
        {"name": "Milk", "calories": 103, "protein": 8.0, "carbs": 12.0, "fat": 2.4, "unit_weight": 250},
        {"name": "Greek Yogurt", "calories": 100, "protein": 10.0, "carbs": 6.0, "fat": 0.7, "unit_weight": 170},
        {"name": "Cheddar Cheese", "calories": 113, "protein": 7.0, "carbs": 0.4, "fat": 9.3, "unit_weight": 28},
        {"name": "Cottage Cheese", "calories": 206, "protein": 23.0, "carbs": 8.2, "fat": 9.7, "unit_weight": 210},

        # Fruits
        {"name": "Banana", "calories": 105, "protein": 1.3, "carbs": 27.0, "fat": 0.3, "unit_weight": 100},
        {"name": "Apple", "calories": 95, "protein": 0.5, "carbs": 25.0, "fat": 0.3, "unit_weight": 182},
        {"name": "Orange", "calories": 62, "protein": 1.2, "carbs": 15.4, "fat": 0.2, "unit_weight": 131},
        {"name": "Strawberries", "calories": 53, "protein": 1.1, "carbs": 12.7, "fat": 0.5, "unit_weight": 166},
        {"name": "Blueberries", "calories": 85, "protein": 1.1, "carbs": 21.5, "fat": 0.5, "unit_weight": 148},
        {"name": "Grapes", "calories": 62, "protein": 0.6, "carbs": 16.0, "fat": 0.3, "unit_weight": 92},
        {"name": "Watermelon", "calories": 46, "protein": 0.9, "carbs": 11.5, "fat": 0.2, "unit_weight": 152},

        # Vegetables
        {"name": "Broccoli", "calories": 55, "protein": 4.6, "carbs": 11.2, "fat": 0.6, "unit_weight": 148},
        {"name": "Spinach", "calories": 23, "protein": 2.9, "carbs": 3.6, "fat": 0.4, "unit_weight": 100},
        {"name": "Carrot", "calories": 25, "protein": 0.6, "carbs": 6.0, "fat": 0.1, "unit_weight": 61},
        {"name": "Tomato", "calories": 22, "protein": 1.1, "carbs": 4.8, "fat": 0.2, "unit_weight": 123},
        {"name": "Cucumber", "calories": 16, "protein": 0.7, "carbs": 3.8, "fat": 0.1, "unit_weight": 100},
        {"name": "Bell Pepper", "calories": 31, "protein": 1.0, "carbs": 6.0, "fat": 0.3, "unit_weight": 119},
        {"name": "Onion", "calories": 44, "protein": 1.2, "carbs": 10.3, "fat": 0.1, "unit_weight": 110},

        # Grains
        {"name": "Oats", "calories": 150, "protein": 5.0, "carbs": 27.0, "fat": 3.0, "unit_weight": 50},
        {"name": "Brown Rice", "calories": 216, "protein": 5.0, "carbs": 44.8, "fat": 1.8, "unit_weight": 195},
        {"name": "Quinoa (Cooked)", "calories": 222, "protein": 8.1, "carbs": 39.4, "fat": 3.6, "unit_weight": 185},
        {"name": "Whole Wheat Bread", "calories": 69, "protein": 3.6, "carbs": 11.6, "fat": 1.1, "unit_weight": 28},

        # Nuts & Seeds
        {"name": "Almonds", "calories": 164, "protein": 6.0, "carbs": 6.1, "fat": 14.2, "unit_weight": 28},
        {"name": "Walnuts", "calories": 185, "protein": 4.3, "carbs": 3.9, "fat": 18.5, "unit_weight": 28},
        {"name": "Chia Seeds", "calories": 137, "protein": 4.4, "carbs": 12.0, "fat": 8.6, "unit_weight": 28},
        {"name": "Peanut Butter", "calories": 188, "protein": 8.0, "carbs": 6.0, "fat": 16.0, "unit_weight": 32},

        # Oils & Fats
        {"name": "Olive Oil", "calories": 119, "protein": 0.0, "carbs": 0.0, "fat": 13.5, "unit_weight": 10},
        {"name": "Butter", "calories": 102, "protein": 0.1, "carbs": 0.0, "fat": 11.5, "unit_weight": 14},
        {"name": "Coconut Oil", "calories": 117, "protein": 0.0, "carbs": 0.0, "fat": 13.6, "unit_weight": 14},

        # Snacks
        {"name": "Dark Chocolate (70%)", "calories": 170, "protein": 2.0, "carbs": 13.0, "fat": 12.0, "unit_weight": 28},
        {"name": "Popcorn (Air-Popped)", "calories": 31, "protein": 1.0, "carbs": 6.2, "fat": 0.4, "unit_weight": 8},

        # Condiments
        {"name": "Soy Sauce", "calories": 8, "protein": 1.3, "carbs": 0.8, "fat": 0.0, "unit_weight": 15},
        {"name": "Honey", "calories": 64, "protein": 0.1, "carbs": 17.3, "fat": 0.0, "unit_weight": 21},
        {"name": "Ketchup", "calories": 20, "protein": 0.2, "carbs": 5.0, "fat": 0.0, "unit_weight": 15},
    ]
    return ingredients

def add_ingredients_to_db():
    """Add ingredients to the database"""
    ingredients = initialize_ingredients()
    for ingredient in ingredients:
        # if the ingredient already exists, update it
        existing_ingredient = Ingredient.query.filter_by(name=ingredient['name']).first()
        if existing_ingredient:
            for key, value in ingredient.items():
                setattr(existing_ingredient, key, value)
        else:
            db.session.add(Ingredient(**ingredient))
    db.session.commit()

if __name__ == "__main__":
    from app import create_app
    app = create_app()
    with app.app_context():
        add_ingredients_to_db()
        print("Ingredients initialized successfully!")