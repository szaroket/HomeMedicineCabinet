from fastapi import FastAPI
import uvicorn

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/health")
async def healt_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app=app, host="localhost", port=8000)
