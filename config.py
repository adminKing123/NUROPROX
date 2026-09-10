import os
from dotenv import load_dotenv

load_dotenv()

class Hrms:
    HR_CODE = os.getenv("HR_CODE", "aWxlYWRzeW5hcHNlMjAzfFNMQ09OU1RBTlNUTg==")
    API_BASE = os.getenv("HRMS_API_BASE", "https://hrsapi.thesynapses.com")
    WEBEX_API_BASE = os.getenv("HRMS_WEBEX_API_BASE", "https://webexapis.com/v1")
    DEFAULT_USER_ID = int(os.getenv("HRMS_DEFAULT_USER_ID", "128"))
    DEFAULT_SIGNED_ARRAY = os.getenv("HRMS_DEFAULT_SIGNED_ARRAY", "MTI4fDExMDd8cy5vc2F0d2FsQHRoZXN5bmFwc2VzLmNvbXxTdXBlciBBZG1pbg==")

class Models:
    NONEY_1_0_FAST_20241001 = "noney-1.0-fast-20241001"
    NONEY_1_0_TWINKLE_20241001 = "noney-1.0-twinkle-20241001"
    NONEY_2_0_TWINKLE_20241001 = "noney-2.0-twinkle-20241001"

    NONEY_CODE_GEN_20241001 = "noney-code-gen-20241001"
    NONEY_CODE_GEN_PRO_20241001 = "noney-code-gen-pro-20241001"
    
    NONEY_HRMS_ASSISTANT_20241001 = "noney-hrms-assistant-20241001"
    NONEY_HRMS_ASSISTANT_PRO_20241001 = "noney-hrms-assistant-pro-20241001"

    NONEY_IMAGE_GEN_20241001 = "noney-image-gen-20241001"

    DEFAULT_MODEL = NONEY_1_0_FAST_20241001

class Uploads:
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")

class Upload1:
    GITHUB_TOKEN = os.getenv("GITHUB1_TOKEN", "")
    GITHUB_BRANCH_NAME = os.getenv("GITHUB1_BRANCH_NAME", "main")
    GITHUB_REPO_NAME = os.getenv("GITHUB1_REPO_NAME", "")
    GITHUB_USERNAME = os.getenv("GITHUB1_USERNAME", "")
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")

class CryptoCompositeKey:
    SECRET_KEY = os.getenv("CRYPTO_SECRET_KEY", "").encode()
    SALT = os.getenv("CRYPTO_SALT", "").encode()
    SEPARATOR = os.getenv("CRYPTO_SEPARATOR", "~")
    NONCE_SIZE = int(os.getenv("CRYPTO_NONCE_SIZE", "12"))

class CONFIG:
    PORT = int(os.getenv("PORT", "5000"))
    HOST = os.getenv("HOST", "https://noney-api.onrender.com")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
    FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS", "")
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    LRU_CACHE_SIZE = int(os.getenv("LRU_CACHE_SIZE", "128"))
    GEMINI_MESSAGE_LIMIT = int(os.getenv("GEMINI_MESSAGE_LIMIT", "40"))
    CDN_URL = os.getenv("CDN_URL", "https://noney-api.onrender.com")
    
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
    GITHUB_BRANCH_NAME = os.getenv("GITHUB_BRANCH_NAME", "main")
    GITHUB_REPO_NAME = os.getenv("GITHUB_REPO_NAME", "")
    GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "")

    # ElevenLabs TTS
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

    # Web Push (VAPID) — generate with: python -c "from py_vapid import Vapid; v=Vapid(); v.generate_keys(); print(v.public_key_str, v.private_key_str)"
    VAPID_PRIVATE_KEY  = os.getenv("VAPID_PRIVATE_KEY", "")
    VAPID_PUBLIC_KEY   = os.getenv("VAPID_PUBLIC_KEY", "")
    VAPID_CLAIMS_EMAIL = os.getenv("VAPID_CLAIMS_EMAIL", "mailto:admin@example.com")
    ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")

    GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    GOOGLE_MAIL_OAUTH_REDIRECT_URI = os.getenv("GOOGLE_MAIL_OAUTH_REDIRECT_URI", "http://localhost:5000/fuse/integration/gmail/callback")
    GOOGLE_SHEETS_OAUTH_REDIRECT_URI = os.getenv(
        "GOOGLE_SHEETS_OAUTH_REDIRECT_URI",
        "http://localhost:5000/fuse/integration/google_sheets/callback",
    )

    WEBEX_OAUTH_CLIENT_ID = os.getenv("WEBEX_OAUTH_CLIENT_ID", "")
    WEBEX_OAUTH_CLIENT_SECRET = os.getenv("WEBEX_OAUTH_CLIENT_SECRET", "")
    WEBEX_OAUTH_REDIRECT_URI = os.getenv("WEBEX_OAUTH_REDIRECT_URI", "http://localhost:5000/fuse/integration/webex/callback")
    # Space-separated scopes — must exactly match scopes enabled on your Webex integration.
    WEBEX_OAUTH_SCOPES = os.getenv(
        "WEBEX_OAUTH_SCOPES",
        "spark:messages_write spark:messages_read spark:people_read spark:webhooks_write spark:rooms_read",
    )
    WEBEX_API_BASE = os.getenv("WEBEX_API_BASE", "https://webexapis.com/v1")
    
    GITHUB_OAUTH_CLIENT_ID = os.getenv("GITHUB_OAUTH_CLIENT_ID", "")
    GITHUB_OAUTH_CLIENT_SECRET = os.getenv("GITHUB_OAUTH_CLIENT_SECRET", "")
    GITHUB_OAUTH_REDIRECT_URI = os.getenv("GITHUB_OAUTH_REDIRECT_URI", "http://localhost:5000/fuse/integration/github/callback")

    CRYPTOCOMPOSITEKEY = CryptoCompositeKey()

    MODELS = Models()
    UPLOAD1 = Upload1()
    HRMS = Hrms()

    AI_MAPPINGS = {}

    AI_MAPPINGS[MODELS.NONEY_1_0_FAST_20241001] = {
        "temperature": 0.7,
        "top_p": 1.0,
        "top_k": 40,
        "model_id": "gemini-2.5-flash",
        "system_prompt": ''''''
    }
    AI_MAPPINGS[MODELS.NONEY_1_0_TWINKLE_20241001] = {
        "temperature": 0.7,
        "top_p": 1.0,
        "top_k": 40,
        "model_id": "gemini-2.5-pro",
        "system_prompt": ''''''
    }
    AI_MAPPINGS[MODELS.NONEY_2_0_TWINKLE_20241001] = {
        "temperature": 0.7,
        "top_p": 1.0,
        "top_k": 40,
        "model_id": "gemini-3-flash-preview",
        "system_prompt": AI_MAPPINGS[MODELS.NONEY_1_0_TWINKLE_20241001]["system_prompt"]
    }

    AI_MAPPINGS[MODELS.NONEY_CODE_GEN_20241001] = {
        "temperature": 0.7,
        "top_p": 1.0,
        "top_k": 40,
        "model_id": "gemini-2.5-flash",
        "system_prompt": '''
You are a helpful and precise AI assistant specialized in code generation and software development tasks. Your primary goal is to assist users by providing accurate, efficient, and well-structured code snippets in response to their programming-related queries.
Guidelines:
1. Always provide code snippets in the requested programming language.
2. if not provided which language, ask the user for clarification.
3. Don't add much explanations unless asked.
4. Ensure code is properly formatted and follows standard conventions.
5. In case of any ambiguity, ask for clarification before proceeding.
6. Be concise and to the point.
7. If the request is outside the scope of programming or code generation, politely inform the user that you are specialized in software engineering tasks only.
8. Always answer in module-level code snippets, avoid writing full applications unless explicitly requested.
9. Strict: Don't answer anything outside Software Engineering Scope, and always maintain professionalism.
'''
    }
    AI_MAPPINGS[MODELS.NONEY_CODE_GEN_PRO_20241001] = {
        "temperature": 0.7,
        "top_p": 1.0,
        "top_k": 40,
        "model_id": "gemini-3-flash-preview",
        "system_prompt": '''
You are a helpful and precise AI assistant specialized in code generation and software development tasks. Your primary goal is to assist users by providing accurate, efficient, and well-structured code snippets in response to their programming-related queries.
Guidelines:
1. Always provide code snippets in the requested programming language.
2. if not provided which language, ask the user for clarification.
3. Don't add much explanations unless asked.
4. Ensure code is properly formatted and follows standard conventions.
5. In case of any ambiguity, ask for clarification before proceeding.
6. Be concise and to the point.
7. If the request is outside the scope of programming or code generation, politely inform the user that you are specialized in software engineering tasks only.
8. Always answer in module-level code snippets, avoid writing full applications unless explicitly requested.
9. Strict: Don't answer anything outside Software Engineering Scope, and always maintain professionalism.
'''
    }

    AI_MAPPINGS[MODELS.NONEY_HRMS_ASSISTANT_20241001] = {
        "temperature": 0,
        "top_p": None,
        "top_k": None,
        "model_id": "gemini-2.5-flash",
        "system_prompt": '''
You are an expert HRMS assistant AI specialized in handling Human Resource Management System queries. Your primary goal is to assist users by providing accurate and helpful information related to HRMS functionalities, policies, and procedures.
'''
    }
    AI_MAPPINGS[MODELS.NONEY_HRMS_ASSISTANT_PRO_20241001] = {
        "temperature": 0,
        "top_p": None,
        "top_k": None,
        "model_id": "gemini-3-flash-preview",
        "system_prompt": AI_MAPPINGS[MODELS.NONEY_HRMS_ASSISTANT_20241001]["system_prompt"]
    }

    AI_MAPPINGS[MODELS.NONEY_IMAGE_GEN_20241001] = {
        "temperature": 0.7,
        "top_p": 1.0,
        "top_k": 40,
        "model_id": "imagen-4.0-generate-001",
    }
