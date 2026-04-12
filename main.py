# main.py — Local development entry point only.
# This file is NOT used inside Docker. Inside Docker, uvicorn is called directly
# via the CMD in the Dockerfile:
#   uvicorn server.api:app --host 0.0.0.0 --port 8000 --reload
#
# Use this file to run the app locally outside Docker:
#   python main.py

import webbrowser

import uvicorn

HOST = "127.0.0.1"
PORT = 8000


if __name__ == "__main__":
    webbrowser.open(f"http://{HOST}:{PORT}")
    uvicorn.run("server.api:app", host=HOST, port=PORT, reload=True)
