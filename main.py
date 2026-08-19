import os
from flask import Flask, request, Response, stream_with_context
import requests

app = Flask(__name__)

URL = "https://photon-api-670504982076.us-central1.run.app/spark/generate"


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True) or {}

    # Request parameters with defaults
    prompt = data.get("prompt")

    model_id = data.get("model_id", "claude-opus-4-6")
    uid = data.get("uid", "zxyz")
    prompt_id = data.get("prompt_id", "xyz2")
    session_id = data.get("session_id", "xyz")
    chat_id = data.get("chat_id", "xyz")
    org_id = data.get("org_id", "synapse")

    # Optional "by"
    by = data.get("by", uid)

    if not prompt:
        return {"error": "prompt is required"}, 400

    payload = {
        "type": "global",
        "prompt": prompt,
        "chat_uid": chat_id,
        "file_url": [],
        "org_id": org_id,
        "uid": uid,
        "regenerate": False,
        "model_id": model_id,
        "recaching": False,
        "cache_id": None,
        "file_data": "",
        "prompt_id": prompt_id,
        "new_prompt": "",
        "by": by,
        "session_id": session_id,
    }

    def stream_response():
        try:
            response = requests.post(
                URL,
                json=payload,
                stream=True,
                timeout=None,
                headers={
                    "Accept": "text/event-stream",
                    "Content-Type": "application/json",
                },
            )

            response.raise_for_status()

            buffer = ""

            for chunk in response.iter_content(
                chunk_size=None,
                decode_unicode=True,
            ):
                if not chunk:
                    continue

                buffer += chunk

                while True:
                    start = buffer.find("SSE_START:")

                    # No SSE wrapper found.
                    # Everything is generated text.
                    if start == -1:
                        if buffer:
                            yield buffer
                            buffer = ""
                        break

                    # Text before SSE_START is generated content
                    if start > 0:
                        content = buffer[:start]
                        yield content
                        buffer = buffer[start:]

                    # SSE event is incomplete
                    end = buffer.find(":SSE_END")

                    if end == -1:
                        break

                    # Remove the complete SSE wrapper
                    buffer = buffer[end + len(":SSE_END"):]

            # Flush remaining generated text
            if buffer and "SSE_START:" not in buffer:
                yield buffer

        except requests.RequestException as e:
            yield f"\nError: {str(e)}"

    return Response(
        stream_with_context(stream_response()),
        content_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        threaded=True,
    )
