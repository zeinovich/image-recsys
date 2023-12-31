"""
App for the frontend

This app is a Streamlit app that allows the user to upload an image and
find similar images in the database.

Usage:
    streamlit run app.py
"""

import streamlit as st
from PIL import Image

import requests
import json
import logging

from io import BytesIO
import base64

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger("frontend")

WIDTH = 360


def decode_image(im_bytes: str) -> Image:
    """
    Decode image from base64

    Args:
        im_bytes (str): Image in base64 format

    Returns:
        Image: Image"""

    img = base64.b64decode(im_bytes.encode("utf-8"))
    image = Image.open(BytesIO(img))
    logger.info(f"Got image of size: {image.size}")
    return image


def predict(img_file: BytesIO) -> dict[dict, str]:
    """
    Send image to backend for classification

    Args:
        img_file (BytesIO): Image file

    Returns:
        dict: Predictions"""

    placeholder = st.empty()
    placeholder.write("Classifying...")

    im_bytes = img_file.getvalue()
    im_b64 = base64.b64encode(im_bytes).decode("utf8")

    logger.info("Turned image into bytes. Preparing JSON request")
    headers = {"Content-type": "application/json", "Accept": "text/plain"}
    payload = json.dumps({"image": im_b64})

    logger.info("Posting request")
    response = requests.post(
        "http://backend:8888/api/v1.0/predict", data=payload, headers=headers
    )

    placeholder.empty()
    if response.status_code == 200:
        predictions = response.json()["predictions"]
        segmented_image = response.json()["segmented_image"]
        logger.info("Succesfully retrived preditions")
        return predictions, segmented_image

    else:
        logger.error("Some error occured during prediction")
        st.write("Error in classification")


def show_image(pred: dict) -> None:
    """
    Show image and product description

    Args:
        pred (dict): Prediction

    Returns:
        None"""

    st.subheader(f"({pred['index']}) {pred['productdisplayname']}")
    col1, col2 = st.columns(2)
    col1.image(pred["default"])
    col2._html(pred["productdescriptors"], scrolling=True, height=450)
    st.write("")


def main():
    st.write("Image similarity search")

    img_file = st.file_uploader("Upload file", type=["png", "jpg", "jpeg"])

    if img_file is not None:
        placeholder = st.empty()
        predictions = None
        logger.info(f"Got image: {type(img_file)}")
        placeholder.image(img_file, width=WIDTH)
        st.write("")

        predictions, segmented_image = predict(img_file)

        if predictions is not None:
            segmented_image = decode_image(segmented_image)
            placeholder.image(segmented_image, width=WIDTH)
            for pred in predictions:
                show_image(pred)

        else:
            st.write("No predictions")


if __name__ == "__main__":
    main()
