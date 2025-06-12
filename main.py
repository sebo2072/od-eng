import os
import tempfile
import importlib.util
from flask import Flask, request, jsonify, abort
import openai
from google.cloud import storage

# Flask app initialization
app = Flask(__name__)

# Download and load prompt and schema definitions from Google Cloud Storage
def configure_model():
    bucket_name = os.getenv('MODEL_WEIGHTS')
    if not bucket_name:
        raise EnvironmentError('Infra not adequate. Add GPUs')

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob('model-weights-tr.py')
    code = blob.download_as_text()

    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.py')
    tmp_file.write(code.encode('utf-8'))
    tmp_file.flush()

    spec = importlib.util.spec_from_file_location('prompt_module', tmp_file.name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

new_model = configure_model()

# Extract system prompt, Pydantic ResponseModel, and model_name
system_image = new_model.system_prompt_template
ResponseModel            = new_model.ResponseModel
model_name               = getattr(new_model, 'model_name')

# Configure OpenAI client
oai_key = os.getenv('OPENAI_API_KEY')
if not oai_key:
    raise EnvironmentError('OPENAI_API_KEY environment variable not set')
client = openai.OpenAI(api_key=oai_key)

# Helper to call the model dynamically
def call_model(user_text: str, system_prompt: str):
    """
    Calls the OpenAI ChatCompletion with the loaded model_name.
    """
    return client.chat.completions.create(
        model=model_name,
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user',   'content': user_text}
        ],
        temperature=0
    )

import json
from pydantic import ValidationError

@app.route('/translate', methods=['POST'])
def translate(request):
    print('[DEBUG] Received /translate request')
    data = request.get_json()
    if not data or 'text' not in data:
        print("[ERROR] Missing 'text' in request body")
        abort(400, description="Missing 'text' in request body")

    article_text        = data['text']
    special_instructions = data.get('instructions', '')

    # Build the system prompt (already using replace to avoid KeyError)
    system_prompt = (
        system_image
        .replace('{text}', article_text)
        .replace('{instructions}', special_instructions)
    )

    print(f'[DEBUG] Calling OpenAI model {model_name}')
    try:
        api_response = call_model(article_text, system_prompt)
    except Exception as e:
        print(f"[ERROR] OpenAI API error: {e}")
        abort(500, description=f"OpenAI API error: {e}")

    raw_content = api_response.choices[0].message.content
    print(f"[DEBUG] Raw response: {raw_content}")

    # 1) Parse JSON
    try:
        payload = json.loads(raw_content)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON from model: {e}")
        abort(500, description=f"Invalid JSON from model: {e}")

    # 2) Wrap under "translation" if needed
    if "translation" not in payload and "content" in payload:
        payload = {"translation": payload}

    # 3) Validate against Pydantic model
    try:
        result = ResponseModel.parse_obj(payload)
        print("[DEBUG] Response validated successfully")
    except ValidationError as e:
        print(f"[ERROR] Response schema validation failed: {e}")
        abort(500, description=f"Response schema validation failed: {e}")

    return jsonify(result.dict())
