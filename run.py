import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="10.36.67.49", port=8001, reload=True)