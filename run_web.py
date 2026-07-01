import uvicorn

if __name__ == "__main__":
    uvicorn.run("web_app.main:app", host="0.0.0.0", port=16320, reload=False)
