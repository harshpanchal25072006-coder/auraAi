import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def show_house_price():

    st.title("🏠 House Price Prediction")
    st.subheader(
        "Train a Linear Regression model and predict house prices."
    )

    st.markdown("---")


    uploaded_file = st.file_uploader(
        "Upload house price CSV file",
        type=["csv"]
    )

    if uploaded_file:
        df = pd.read_csv(uploaded_file)

    else:
        df = pd.DataFrame(
            {
                "LotArea": [
                    1500, 1800, 2000, 2200, 2500,
                    2800, 3000, 3500, 4000, 4500
                ],
                "Bedrooms": [
                    2, 3, 3, 3, 4,
                    4, 4, 5, 5, 6
                ],
                "HouseAge": [
                    20, 15, 12, 10, 8,
                    7, 5, 4, 3, 2
                ],
                "GarageArea": [
                    200, 250, 300, 350, 400,
                    450, 500, 550, 600, 700
                ],
                "SalePrice": [
                    150000, 180000, 200000, 220000, 250000,
                    280000, 310000, 360000, 420000, 480000
                ]
            }
        )

        st.info(
            "No CSV uploaded. Using generated sample house price dataset."
        )

    st.subheader("📊 House Price Dataset")

    st.dataframe(
        df.head(20),
        use_container_width=True
    )

    required_cols = [
        "LotArea",
        "Bedrooms",
        "HouseAge",
        "GarageArea",
        "SalePrice"
    ]

    missing_cols = [
        col for col in required_cols
        if col not in df.columns
    ]

    if missing_cols:

        st.warning(
            f"Dataset must contain these columns: {missing_cols}"
        )

        return


    clean_df = df[required_cols].drop_duplicates()

    clean_df = clean_df.fillna(
        clean_df.mean(numeric_only=True)
    )

    features = clean_df[
        [
            "LotArea",
            "Bedrooms",
            "HouseAge",
            "GarageArea"
        ]
    ]

 
    target = clean_df["SalePrice"]


    X_train, X_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=0.2,
        random_state=42
    )

  
    model = LinearRegression()


    model.fit(
        X_train,
        y_train
    )


    predictions = model.predict(X_test)

    mae = mean_absolute_error(
        y_test,
        predictions
    )

    mse = mean_squared_error(
        y_test,
        predictions
    )

    r2 = r2_score(
        y_test,
        predictions
    )


    st.markdown("---")
    st.subheader("🤖 Model Performance")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "MAE",
            f"{mae:,.0f}"
        )

    with c2:
        st.metric(
            "MSE",
            f"{mse:,.0f}"
        )

    with c3:
        st.metric(
            "R² Score",
            f"{r2:.2f}"
        )

    st.markdown("---")
    st.subheader("🏠 Predict New House Price")

    p1, p2, p3, p4 = st.columns(4)

    with p1:
        lot_area = st.number_input(
            "Lot Area",
            min_value=1,
            value=1800
        )

    with p2:
        bedrooms = st.number_input(
            "Bedrooms",
            min_value=1,
            value=3
        )

    with p3:
        house_age = st.number_input(
            "House Age",
            min_value=0,
            value=10
        )

    with p4:
        garage_area = st.number_input(
            "Garage Area",
            min_value=0,
            value=350
        )

    user_input = pd.DataFrame(
        [
            [
                lot_area,
                bedrooms,
                house_age,
                garage_area
            ]
        ],
        columns=[
            "LotArea",
            "Bedrooms",
            "HouseAge",
            "GarageArea"
        ]
    )

    predicted_price = model.predict(
        user_input
    )[0]

    st.success(
        f"💰 Predicted House Price: ₹{predicted_price:,.0f}"
    )

    st.markdown("---")
    st.subheader("📈 Actual vs Predicted Price")

    fig, ax = plt.subplots(
        figsize=(7, 5)
    )

    ax.scatter(
        y_test,
        predictions
    )

    ax.set_xlabel(
        "Actual Price"
    )

    ax.set_ylabel(
        "Predicted Price"
    )

    ax.set_title(
        "Actual vs Predicted House Price"
    )

    st.pyplot(fig)

