import httpx
import os
from modules.const import Config
from telegram import Bot
import logging
import asyncio
import json as pyjson

SPEECHMATICS_API_URL = "https://asr.api.speechmatics.com/v2/jobs/"

async def transcribe_telegram_voice(bot: Bot, file_id: str, language: str = "uk") -> str:
    """
    Download a Telegram voice or video_note file and send it to Speechmatics for transcription.
    Returns the transcribed text, or raises an exception on error.
    """
    if not Config.SPEECHMATICS_API_KEY:
        raise RuntimeError("Speechmatics API key is not set. Please set SPEECHMATICS_API_KEY in your environment.")

    # Download the file from Telegram
    file = await bot.get_file(file_id)
    file_bytes = bytes(await file.download_as_bytearray())  # Convert to bytes

    # Prepare headers and data for Speechmatics
    headers = {
        "Authorization": f"Bearer {Config.SPEECHMATICS_API_KEY}",
    }
    # Create the job (multipart/form-data, config + data_file together)
    async with httpx.AsyncClient() as client:
        job_config = {
            "type": "transcription",
            "transcription_config": {
                "language": language
            }
        }
        job_resp = await client.post(
            SPEECHMATICS_API_URL,
            headers=headers,
            files={
                "config": (None, pyjson.dumps(job_config), "application/json"),
                "data_file": ("voice.ogg", file_bytes, "audio/ogg")
            }
        )
        if job_resp.status_code >= 400:
            raise RuntimeError(f"Speechmatics job creation failed: {job_resp.status_code} {job_resp.text}")
        job_resp.raise_for_status()
        job_id = job_resp.json()["id"]
        # 2. Wait for the job to complete
        status_url = f"{SPEECHMATICS_API_URL}{job_id}/"
        for _ in range(30):  # Wait up to ~30 seconds
            status_resp = await client.get(status_url, headers=headers)
            status_resp.raise_for_status()
            job_json = status_resp.json()
            job_info = job_json.get("job", {})
            if "status" not in job_info:
                raise RuntimeError(f"Speechmatics job status missing 'status' key. Full response: {job_json}")
            status = job_info["status"]
            if status == "done":
                break
            elif status == "failed":
                raise RuntimeError(f"Speechmatics job failed: {status_resp.text}")
            await asyncio.sleep(1)
        else:
            raise TimeoutError("Speechmatics transcription timed out.")
        # 3. Get the transcript
        transcript_url = f"{SPEECHMATICS_API_URL}{job_id}/transcript?format=txt"
        transcript_resp = await client.get(transcript_url, headers=headers)
        transcript_resp.raise_for_status()
        return transcript_resp.text.strip() 