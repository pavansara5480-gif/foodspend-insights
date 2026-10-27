"""Synthetic catalogue used by the data generator.

All vendors, prices, and nutrient values are SYNTHETIC ESTIMATES. Nutrient values
approximate typical published values for similar Indian dishes and raw foods
(e.g. IFCT 2017, USDA FoodData Central), but they were not looked up item by item
and must not be treated as measured composition data.
"""

# vendor_id, vendor_name, channel, tax_rate, typical_delivery_fee
VENDORS = [
    ("V01", "Tiffin Centre (synthetic)", "delivery", 0.05, 30),
    ("V02", "Punjabi Dhaba (synthetic)", "delivery", 0.05, 35),
    ("V03", "Biryani House (synthetic)", "delivery", 0.05, 40),
    ("V04", "Green Bowl Co. (synthetic)", "delivery", 0.05, 35),
    ("V05", "Wok Express (synthetic)", "delivery", 0.05, 30),
    ("V06", "Pizza Point (synthetic)", "delivery", 0.05, 40),
    ("V07", "Neighbourhood Grocery (synthetic)", "grocery", 0.0, 0),
    ("V08", "Home Kitchen", "home", 0.0, 0),
    ("V09", "Corner Cafe (synthetic)", "cafe", 0.05, 0),
]

# Columns:
# food_id, name, category, role, vendor_id, serving_size, unit, base_price,
# basis, basis_qty, kcal, protein, carbs, fat, fiber (None = unknown), true_rating
# base_price is per serving for per_serving foods; per basis quantity (100 g/ml) for per_100 foods.
FOODS = [
    ("F001", "Masala Dosa", "South Indian", "main", "V01", 250, "g", 110, "per_serving", 250, 420, 9, 62, 15, 5, 4.3),
    ("F002", "Idli Sambar (3 idli)", "South Indian", "main", "V01", 300, "g", 80, "per_serving", 300, 330, 11, 62, 4, 6, 4.0),
    ("F003", "Ven Pongal", "South Indian", "main", "V01", 250, "g", 90, "per_serving", 250, 390, 10, 55, 14, 3, 3.4),
    ("F004", "Paneer Butter Masala with 2 Roti", "North Indian", "main", "V02", 400, "g", 240, "per_serving", 400, 720, 26, 60, 42, 6, 4.6),
    ("F005", "Dal Tadka with Jeera Rice", "North Indian", "main", "V02", 400, "g", 180, "per_serving", 400, 560, 18, 88, 14, 9, 3.9),
    ("F006", "Chicken Biryani", "Biryani", "main", "V03", 450, "g", 260, "per_serving", 450, 780, 34, 95, 28, 4, 4.7),
    ("F007", "Veg Biryani", "Biryani", "main", "V03", 400, "g", 200, "per_serving", 400, 620, 13, 98, 19, 6, 3.5),
    ("F008", "Grilled Chicken Salad Bowl", "Bowls & Salads", "main", "V04", 350, "g", 280, "per_serving", 350, 410, 38, 22, 18, 7, 4.2),
    ("F009", "Rajma Brown Rice Bowl", "Bowls & Salads", "main", "V04", 400, "g", 220, "per_serving", 400, 540, 21, 85, 11, 14, 4.1),
    ("F010", "Paneer Tikka Bowl", "Bowls & Salads", "main", "V04", 350, "g", 260, "per_serving", 350, 520, 30, 38, 26, 8, 4.4),
    ("F011", "Chole Bhature", "North Indian", "main", "V02", 350, "g", 170, "per_serving", 350, 820, 20, 96, 40, 11, 2.0),
    ("F012", "Egg Curry with 2 Roti", "North Indian", "main", "V02", 380, "g", 170, "per_serving", 380, 560, 25, 52, 26, 6, 3.8),
    ("F013", "Veg Hakka Noodles", "Indo-Chinese", "main", "V05", 350, "g", 180, "per_serving", 350, 610, 12, 92, 21, None, 3.0),
    ("F014", "Chicken Fried Rice", "Indo-Chinese", "main", "V05", 400, "g", 210, "per_serving", 400, 690, 26, 96, 22, 3, 3.6),
    ("F015", "Margherita Pizza (half medium)", "Fast Food", "main", "V06", 250, "g", 220, "per_serving", 250, 640, 26, 78, 24, 4, 3.9),
    ("F016", "Veg Burger with Fries", "Fast Food", "main", "V06", 300, "g", 190, "per_serving", 300, 720, 15, 88, 34, None, 3.2),
    ("F017", "Moong Dal Khichdi", "South Indian", "main", "V01", 350, "g", 120, "per_serving", 350, 410, 16, 68, 8, 8, 3.3),
    ("F018", "Sprouts Chaat", "Bowls & Salads", "main", "V04", 200, "g", 120, "per_serving", 200, 210, 13, 32, 3, 9, 4.3),
    ("F019", "Fish Curry Meal", "Biryani", "main", "V03", 450, "g", 280, "per_serving", 450, 650, 36, 78, 20, 5, 1.5),
    ("F020", "Poha", "South Indian", "main", "V01", 200, "g", 60, "per_serving", 200, 270, 6, 46, 7, 3, 3.8),
    # Grocery / pantry items: nutrients per 100 g, price per 100 g
    ("F021", "Curd (Dahi)", "Dairy", "pantry", "V07", 150, "g", 12, "per_100g", 100, 61, 3.5, 4.7, 3.3, 0, 4.0),
    ("F022", "Banana", "Fruit", "pantry", "V07", 120, "g", 5, "per_100g", 100, 89, 1.1, 22.8, 0.3, 2.6, 3.7),
    ("F023", "Boiled Eggs", "Eggs", "pantry", "V07", 100, "g", 14, "per_100g", 100, 155, 13, 1.1, 11, 0, 3.9),
    ("F024", "Roasted Chana", "Snacks", "pantry", "V07", 40, "g", 30, "per_100g", 100, 369, 22, 58, 5, 17, 3.4),
    ("F025", "Apple", "Fruit", "pantry", "V07", 150, "g", 20, "per_100g", 100, 52, 0.3, 14, 0.2, 2.4, 3.8),
    ("F026", "Mixed Nuts", "Snacks", "pantry", "V07", 30, "g", 100, "per_100g", 100, 607, 20, 21, 54, 7, 4.2),
    # Home-prepared meals: estimated ingredient cost per serving
    ("F027", "Home Dal, Rice and Sabzi Thali", "Home-cooked", "main", "V08", 450, "g", 70, "per_serving", 450, 520, 18, 85, 12, 10, 3.9),
    ("F028", "Home Oats with Milk", "Home-cooked", "main", "V08", 250, "g", 35, "per_serving", 250, 290, 12, 45, 7, 5, 3.4),
    ("F029", "Home Vegetable Upma", "Home-cooked", "main", "V08", 250, "g", 30, "per_serving", 250, 300, 7, 45, 10, 4, 3.2),
    ("F030", "Home Paneer Bhurji with 2 Roti", "Home-cooked", "main", "V08", 300, "g", 80, "per_serving", 300, 520, 26, 40, 28, 5, 4.2),
    # Cafe snacks and beverages
    ("F031", "Masala Chai", "Beverages", "beverage", "V09", 150, "ml", 25, "per_serving", 150, 110, 3, 15, 4, 0, 4.0),
    ("F032", "Cold Coffee", "Beverages", "beverage", "V09", 300, "ml", 120, "per_serving", 300, 260, 7, 38, 9, 0, 4.4),
    ("F033", "Samosa (2 pcs)", "Snacks", "snack", "V09", 140, "g", 50, "per_serving", 140, 520, 8, 52, 31, 4, 4.1),
    ("F034", "Gulab Jamun (2 pcs)", "Desserts", "snack", "V09", 100, "g", 70, "per_serving", 100, 380, 5, 58, 15, 1, 4.8),
    ("F035", "Fresh Lime Soda", "Beverages", "beverage", "V09", 300, "ml", 60, "per_serving", 300, 90, 0, 23, 0, 0, 3.6),
    ("F036", "Veg Sandwich", "Snacks", "snack", "V09", 180, "g", 90, "per_serving", 180, 330, 10, 45, 12, 4, 3.5),
    ("F037", "Buttermilk (Chaas)", "Beverages", "beverage", "V09", 250, "ml", 30, "per_serving", 250, 90, 5, 9, 3, 0, 3.9),
    ("F038", "Banana Peanut Smoothie", "Beverages", "beverage", "V04", 350, "ml", 150, "per_serving", 350, 380, 14, 52, 13, 5, 4.0),
    # Vendor sides
    ("F039", "Cucumber Raita", "Sides", "side", "V02", 150, "g", 60, "per_serving", 150, 90, 4, 8, 4, 1, 3.8),
    ("F040", "Green Salad", "Sides", "side", "V04", 120, "g", 50, "per_serving", 120, 40, 2, 8, 0, 3, 3.0),
]

# Pack sizes for grocery purchases: food_id -> (quantity, pack_size_g)
GROCERY_PACKS = {
    "F021": (1, 500),   # curd 500 g tub
    "F022": (6, 120),   # 6 bananas of ~120 g
    "F023": (1, 600),   # 12 eggs ~600 g
    "F024": (1, 500),
    "F025": (1, 1000),
    "F026": (1, 250),
}

# Which meal types each food can be ordered for (meal options for recommendation)
MEAL_TYPES = {
    "F001": ["breakfast", "lunch", "dinner"], "F002": ["breakfast", "lunch"], "F003": ["breakfast"],
    "F004": ["lunch", "dinner"], "F005": ["lunch", "dinner"], "F006": ["lunch", "dinner"],
    "F007": ["lunch", "dinner"], "F008": ["lunch", "dinner"], "F009": ["lunch", "dinner"],
    "F010": ["lunch", "dinner"], "F011": ["lunch"], "F012": ["lunch", "dinner"],
    "F013": ["lunch", "dinner"], "F014": ["lunch", "dinner"], "F015": ["lunch", "dinner"],
    "F016": ["lunch", "dinner", "snack"], "F017": ["lunch", "dinner"], "F018": ["lunch", "snack"],
    "F019": ["lunch", "dinner"], "F020": ["breakfast"],
    "F021": ["breakfast", "lunch", "dinner", "snack"], "F022": ["breakfast", "lunch", "snack"],
    "F023": ["breakfast", "lunch", "dinner", "snack"], "F024": ["lunch", "snack"],
    "F025": ["breakfast", "lunch", "snack"], "F026": ["snack"],
    "F027": ["lunch", "dinner"], "F028": ["breakfast"], "F029": ["breakfast"], "F030": ["lunch", "dinner"],
    "F031": ["breakfast", "snack"], "F032": ["snack"], "F033": ["snack"], "F034": ["snack", "dinner"],
    "F035": ["lunch", "snack"], "F036": ["breakfast", "snack"], "F037": ["lunch", "snack"],
    "F038": ["breakfast", "snack"], "F039": ["lunch", "dinner"], "F040": ["lunch", "dinner"],
}

# Allowed serving multipliers for meal options
ALLOWED_SERVINGS = {
    "main_delivery": "1,2",
    "main_home": "1,1.5",
    "pantry": "0.5,1,2",
    "other": "1",
}

# Names as they appear in raw order exports, used to exercise the name-matching rules
RAW_NAME_VARIANTS = {
    "F001": [" masala dosa", "MASALA DOSA", "Masala  Dosa"],
    "F004": ["Paneer Butter Masala w/ 2 Roti", "paneer butter masala with 2 roti"],
    "F013": ["Veg. Hakka Noodles", "veg hakka noodles "],
    "F027": ["Home Dal Rice Sabzi Thali", "home dal, rice and sabzi thali"],
}

FEEDBACK_COMMENTS = {
    5: ["Loved it", "Excellent, would order again", "Great taste and portion"],
    4: ["Tasty", "Good, satisfying meal", "Nice, slightly salty"],
    3: ["Okay, convenient", "Average taste", "Fine but nothing special"],
    2: ["Too oily and heavy", "Did not enjoy it", "Portion felt too heavy"],
    1: ["Not for me", "Would not order again"],
}
