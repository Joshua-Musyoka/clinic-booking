from fastapi import FastAPI

from app.config import get_settings
from app.routers import appointments, doctors, patients

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Savannah Clinic appointment booking API.",
)

app.include_router(appointments.router)
app.include_router(doctors.router)
app.include_router(patients.router)

@app.get("/health", tags=["Health"])
def health_check():
    return {
        "success": True,
        "message": "Savannah Clinic Booking API is running.",
    }