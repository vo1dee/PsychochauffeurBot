"""
Main FastAPI application for the PsychochauffeurBot API.
"""
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .routers import reminders
from modules.logger import error_logger

# Initialize FastAPI app
app = FastAPI(
    title="PsychochauffeurBot API",
    description="REST API for the PsychochauffeurBot Telegram bot",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Set to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(reminders.router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for all unhandled exceptions"""
    error_path = request.url.path
    error_logger.error(f"Unhandled API exception at {error_path}: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please check the logs."}
    )


@app.get("/")
async def root():
    """Root endpoint to verify API is running"""
    return {"message": "PsychochauffeurBot API is running"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}