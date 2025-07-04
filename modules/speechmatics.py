import httpx
import os
from modules.const import Config
from telegram import Bot
import logging
import asyncio
import json as pyjson

SPEECHMATICS_API_URL = "https://asr.api.speechmatics.com/v2/jobs/"

class SpeechmaticsLanguageNotExpected(Exception):
    pass

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
    file_size_kb = len(file_bytes) / 1024
    logging.info(f"[Speechmatics] Downloaded file_id={file_id}, size={file_size_kb:.1f} KB")
    
    headers = {
        "Authorization": f"Bearer {Config.SPEECHMATICS_API_KEY}",
    }
    max_retries = 3
    attempt = 1
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            job_config = {
                "type": "transcription",
                "transcription_config": {
                    "language": language
                }
            }
            if language == "auto":
                job_config["language_identification_config"] = {
                    "expected_languages": ["en", "he", "uk"]
                }
            logging.info(f"[Speechmatics] Creating job with config: {pyjson.dumps(job_config)}")
            job_resp = await client.post(
                SPEECHMATICS_API_URL,
                headers=headers,
                files={
                    "config": (None, pyjson.dumps(job_config), "application/json"),
                    "data_file": ("voice.ogg", file_bytes, "audio/ogg")
                }
            )
            logging.info(f"[Speechmatics] Job creation response: {job_resp.status_code} {job_resp.text}")
            if job_resp.status_code >= 400:
                # Check for 'not one of the expected languages' error
                if "not one of the expected languages" in job_resp.text:
                    logging.warning(f"Speechmatics identified language not expected: {job_resp.text}")
                    raise SpeechmaticsLanguageNotExpected(job_resp.text)
                logging.error(f"Speechmatics job creation failed (attempt {attempt}): {job_resp.status_code} {job_resp.text}")
                job_resp.raise_for_status()
            job_id = job_resp.json()["id"]
            status_url = f"{SPEECHMATICS_API_URL}{job_id}/"
            # Poll for up to 60 seconds (60 tries, 1s interval)
            for poll_num in range(60):
                try:
                    status_resp = await client.get(status_url, headers=headers)
                    status_resp.raise_for_status()
                    job_json = status_resp.json()
                    logging.info(f"[Speechmatics] Poll {poll_num+1}/60: job status response: {job_json}")
                    job_info = job_json.get("job", {})
                    if "status" not in job_info:
                        logging.error(f"Speechmatics job status missing 'status' key. Full response: {job_json}")
                        raise RuntimeError(f"Speechmatics job status missing 'status' key. Full response: {job_json}")
                    status = job_info["status"]
                    if status == "done":
                        logging.info(f"[Speechmatics] Job {job_id} done after {poll_num+1} polls.")
                        break
                    elif status == "failed" or status == "rejected":
                        # Check for 'not one of the expected languages' error in failure/rejection
                        if "not one of the expected languages" in status_resp.text:
                            logging.warning(f"Speechmatics identified language not expected: {status_resp.text}")
                            raise SpeechmaticsLanguageNotExpected(status_resp.text)
                        logging.error(f"Speechmatics job {status}: {status_resp.text}")
                        raise RuntimeError(f"Speechmatics job {status}: {status_resp.text}")
                    await asyncio.sleep(1.0)
                except Exception as e:
                    logging.error(f"Error polling Speechmatics job status (attempt {attempt}, poll {poll_num+1}): {e}")
                    if isinstance(e, SpeechmaticsLanguageNotExpected):
                        raise  # Immediately break out of the polling loop
                    if poll_num == 59:
                        raise
                    await asyncio.sleep(1.0)
            else:
                logging.error("Speechmatics transcription timed out after 60 seconds.")
                raise TimeoutError("Speechmatics transcription timed out.")
            # 3. Get the transcript
            transcript_url = f"{SPEECHMATICS_API_URL}{job_id}/transcript?format=txt"
            try:
                transcript_resp = await client.get(transcript_url, headers=headers)
                logging.info(f"[Speechmatics] Transcript fetch response: {transcript_resp.status_code} {transcript_resp.text}")
                transcript_resp.raise_for_status()
                transcript_text = transcript_resp.text.strip()
                logging.info(f"[Speechmatics] Transcript text: {transcript_text}")
                return transcript_text
            except Exception as e:
                logging.error(f"[Speechmatics] Error fetching transcript for job {job_id}: {e}")
                raise
    except Exception as e:
        logging.error(f"Speechmatics transcription error (attempt {attempt}): {e}")
        raise 