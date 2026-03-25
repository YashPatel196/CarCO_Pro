import pandas as pd
import pickle
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

# =========================
# LOAD DATA
# =========================
data = pd.read_csv('CO2_Emissions_Canada.csv')

# --- BALANCING LOGIC ---
data['Log_Fuel'] = np.log1p(data['Fuel Consumption Comb (L/100 km)'])
data['Engine_Cyl_Ratio'] = data['Engine Size(L)'] / data['Cylinders']

# Instead of a standalone fuel feature, create a ratio:
data['Fuel_per_Liter'] = data['Log_Fuel'] / (data['Engine Size(L)'] + 1)

features = [
    'Engine Size(L)',
    'Cylinders',
    'Fuel_per_Liter',
    'Engine_Cyl_Ratio',
    'Fuel Type',
    'Vehicle Class',
    'Transmission'
]

X = data[features]
y = data['CO2 Emissions(g/km)']

# =========================
# ONE HOT ENCODING
# =========================
X = pd.get_dummies(X, columns=['Fuel Type', 'Vehicle Class', 'Transmission'])
model_columns = list(X.columns)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# =========================
# BALANCED MODEL PARAMETERS
# =========================
# max_features=3 forces the model to use other features in most of its trees
params = {
    'learning_rate': 0.005, 
    'n_estimators': 2000,
    'max_depth': 4,
    'max_features': 4,     # <--- Key change for equal distribution
    'subsample': 0.8,
    'random_state': 42
}

print("Training Balanced Multi-Feature Models...")
lower_model = GradientBoostingRegressor(loss="quantile", alpha=0.025, **params).fit(X_train, y_train)
mid_model = GradientBoostingRegressor(loss="squared_error", **params).fit(X_train, y_train)
upper_model = GradientBoostingRegressor(loss="quantile", alpha=0.975, **params).fit(X_train, y_train)

# =========================
# RESULTS & IMPORTANCE
# =========================
y_pred = mid_model.predict(X_test)
print(f"\nNew R2 Score: {r2_score(y_test, y_pred):.4f}")

importances = mid_model.feature_importances_
importance_df = pd.DataFrame({'Feature': X.columns, 'Importance': importances}).sort_values(by='Importance', ascending=False)
print("\n=== DISTRIBUTED FEATURE IMPORTANCE ===")
print(importance_df.head(10))

# Save Bundle
bundle = {'lower': lower_model, 'mid': mid_model, 'upper': upper_model, 'columns': model_columns}
with open('ultimate_confidence_model_V2.pkl', 'wb') as f:
    pickle.dump(bundle, f)