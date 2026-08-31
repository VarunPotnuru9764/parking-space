from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def root():
    return {"message": "Parking Space Detection System API is running"}