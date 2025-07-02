#!/bin/bash

# Create a layer with Python dependencies
mkdir -p layer/python
pip install -r requirements.txt -t layer/python/
cd layer && zip -r ../dependencies-layer.zip .
cd ..
rm -rf layer