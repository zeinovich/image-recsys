from flask import Flask, request, jsonify
from PIL import Image
from feature_extractor.extractor import FeatureExtractor
from ranker.ranker import Ranker
from io import BytesIO
from sqlalchemy import create_engine
import pandas as pd
import pickle
import logging
import base64
from dotenv import load_dotenv
from os import getenv

load_dotenv("./backend.env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler("./logs/backend.log"), logging.StreamHandler()],
)

logger = logging.getLogger("backend")

FEATURE_EXTRACTOR_PATH = getenv("FEATURE_EXTRACTOR_PATH")
RANKER_PATH = getenv("RANKER_PATH")
SCALER_PATH = getenv("SCALER_PATH")

USER = getenv("POSTGRES_USER")
PASSWORD = getenv("POSTGRES_PASSWORD")
DB = getenv("POSTGRES_DB")

logger.info(f"{FEATURE_EXTRACTOR_PATH=}")
logger.info(f"{RANKER_PATH=}")
logger.info(f"{SCALER_PATH=}")

assert USER is not None, "Got None db username"
assert PASSWORD is not None, "Got None db password"
assert DB is not None, "Got None db name"

logger.info("Successfully loaded environment")
try:
    with open(SCALER_PATH, "rb") as f:
        scaler = pickle.load(f)

except Exception as e:
    logger.error(f"Error loading scaler: {e}")
    logger.info("Setting scaler to None")
    scaler = None

try:
    feature_extractor = FeatureExtractor(FEATURE_EXTRACTOR_PATH, scaler=scaler)
    ranker = Ranker(RANKER_PATH)

except Exception as e:
    logger.error(f"Error loading model: {e}")
    raise e

try:
    connection = f"postgresql://{USER}:{PASSWORD}@postgres:5432/{DB}"
    engine = create_engine(connection)
    logger.info("Connected to DB")

except Exception as e:
    logger.error(f"Error connecting to DB: {e}")
    raise e

app = Flask(__name__)


def get_predictions(data: dict) -> list:
    image = data["image"]
    logger.info(f"Got image: {type(image)}")

    image = Image.open(BytesIO(base64.b64decode(image)))
    logger.info(f"Opened image: {type(image)} of size: {image.size}")

    features = feature_extractor.extract(image)
    logger.info(f"Extracted features: {features.shape}")

    predictions = ranker.rank(features)
    distances, ids = (predictions[0].tolist(), predictions[1].tolist())

    logger.info(f"Predictions: {predictions}")

    return distances, ids


def get_info_from_db(predictions: list):
    distances = predictions[0]
    ids = tuple(predictions[1])

    ids_dist = pd.DataFrame(data=[ids, distances]).T
    ids_dist.columns = ["id", "distance"]

    logger.info(f"Got ids: {ids}")
    logger.info(f"Got ids_dist: {ids_dist}")

    query = f"""
    SELECT *
    FROM styles_v1 as t
    WHERE index IN {ids}
    """

    logger.info(f"Query: {query}")

    try:
        df = pd.read_sql(query, engine)
        logger.info(f"Got df: {df.shape}")
        df = (
            pd.merge(
                left=df, right=ids_dist, how="left", left_on="index", right_on="id"
            )
            .sort_values("distance", ascending=True)
            .reset_index(drop=True)
        )

        logger.info(f"Sorted {df.distance}")

        predictions = df.to_dict(orient="records")
        logger.info(f'Got predictions: {[pred["index"] for pred in predictions]}')

        return predictions

    except Exception as e:
        logger.error(f"Error getting info from DB: {e}")


@app.route("/api/v1.0/predict", methods=["POST"])
def predict():

    logger.info("Got request")

    try:
        data = request.get_json()
        logger.info(f"Got JSON: {type(data)}")

        prediction = get_predictions(data)
        predictions_urls = get_info_from_db(prediction)

        return jsonify({"predictions": predictions_urls, "status_code": 200})

    except Exception as e:
        logger.error(f"Error in predict: {e}")
        return jsonify({"error": f"{e}", "status_code": 400})


@app.route("/api/v1.0/health", methods=["GET"])
def health():
    return jsonify({"status": 200})


if __name__ == "__main__":
    app.run(debug=True, host="localhost", port=8888)