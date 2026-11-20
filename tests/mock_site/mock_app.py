import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="Mock Signup & Login Site")

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
SIGNUP_TEMPLATE = os.path.join(TEMPLATE_DIR, "mock_signup.html")
LOGIN_TEMPLATE = os.path.join(TEMPLATE_DIR, "mock_login.html")

@app.get("/signup", response_class=HTMLResponse)
async def get_signup_page():
    with open(SIGNUP_TEMPLATE, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/login", response_class=HTMLResponse)
async def get_login_page():
    with open(LOGIN_TEMPLATE, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "mock-signup-server"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
