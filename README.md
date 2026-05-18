# 🚀 Crypto Execution Optimizer: Late Capital Deployment

![Databricks](https://img.shields.io/badge/Databricks-FF3621?style=for-the-badge&logo=Databricks&logoColor=white)
![PySpark](https://img.shields.io/badge/PySpark-E25A1C?style=for-the-badge&logo=Apache-Spark&logoColor=white)
![MLflow](https://img.shields.io/badge/MLflow-0194E2?style=for-the-badge&logo=MLflow&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)

**Live Demo:** [Link to Streamlit App](https://crypto-pipeline-azkbkrdaiayjz3exyugwya.streamlit.app/)

## 📌 Project Overview
This project presents an **End-to-End MLOps Pipeline** designed to optimize the execution strategy for **Late Capital Deployment** in cryptocurrency momentum trading. 

When a low-frequency momentum signal triggers, but new capital arrives days later, traders face a paradox: executing via market orders risks buying the local top, while placing deep limit orders risks missing the trend entirely. This project solves this by using Machine Learning to predict the optimal **Volatility-Adjusted Pyramid Execution Strategy (ATR-based scaling)** over a 72-hour window.

## 🏗️ Architecture & Pipeline
Data is ingested from AWS Lambda into Amazon S3 (Landing Zone). Within Databricks, we employ a **Delta Lakehouse Medallion Architecture**:

1. **Data Engineering (PySpark & Delta Lake)**
   * **Bronze Layer:** Houses the raw data ingested from S3, ensuring a single source of truth.
   * **Silver Layer:** Cleansed and standardized data where timestamps are normalized and schema enforcement is applied using PySpark and Delta format.
   * **Gold Layer:** Aggregated, high-order features optimized for Machine Learning models and analytics.
2. **Machine Learning (FLAML & MLflow)**
   * Utilizes **FLAML** for automated model training.
   * Managed via **MLflow** for experiment tracking and model registry.
3. **Model Serving (Databricks Serverless)**
   * The final model is deployed via **Databricks Serverless Model Serving**, exposing a REST API.
4. **User Interface (Streamlit)**
   * The REST API powers a publicly hosted **Streamlit** web application.

## 🧠 Execution Strategies (The Labels)
The model classifies current market micro-structures into one of three optimal execution templates:
* **Strategy A (Aggressive):** 50% Market Order / 50% Limit Order at 0.5x ATR.
* **Strategy B (Balanced):** 30% Market Order / 40% Limit Order at 1.5x ATR / 30% at 2.0x ATR.
* **Strategy C (Passive):** 10% Market Order / 90% Deep Limit Orders (2.0x to 4.0x ATR).

## 🛠️ Technology Stack
* **Cloud Platform:** Databricks Serverless
* **Data Ingestion:** AWS Lambda, Amazon S3
* **Data Processing:** Apache Spark (PySpark), Delta Lake
* **Machine Learning:** FLAML (AutoML), scikit-learn
* **MLOps:** MLflow, Databricks Model Registry, Model Serving Endpoints
* **Web Application:** Streamlit

## 💻 How to Run the Web App (Streamlit)

### Prerequisites
1. Python 3.9+
2. A valid Databricks Personal Access Token (PAT)
3. The deployed Databricks Serving Endpoint URL

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/peteryds/crypto-pipeline.git
   cd crypto-pipeline
   ```

2. Set up a Virtual Environment (Recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up your Databricks credentials. Create a .streamlit/secrets.toml file and add:
   ```bash
   DATABRICKS_TOKEN = "your-personal-access-token"
   DATABRICKS_URL = "your-serving-endpoint-url"
   ```

   Create a `.env` file in the root directory and add your AWS credentials:
   ```env
   S3_BUCKET_NAME=your-bucket-name
   AWS_ACCESS_KEY_ID=your-access-key
   AWS_SECRET_ACCESS_KEY=your-secret-key
   ```
### Launch the App
   ```env
   streamlit run app.py
   ```

## 🧪 Running the Test Script

To verify the Databricks Model Serving endpoint, you can run the provided test script. 

1. Ensure you have the required packages installed:
   ```bash
   pip install requests python-dotenv
   ```
2. Make sure your `.env` file contains your `DATABRICKS_TOKEN` and `DATABRICKS_URL` as mentioned in the prerequisites.
3. Execute the script from the root directory:
   ```bash
   python test/test_project.py
   ```

## 🤝 Acknowledgments
Developed as the final project for Distributed Computing Course at New College of Florida.