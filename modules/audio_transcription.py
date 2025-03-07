"""
Audio transcription module for PsychoChauffeur bot.
Handles voice message and video note (circle video) processing and transcription using Whisper AI locally.
Supports English and Ukrainian languages.
"""
import os
import logging
from pydub import AudioSegment
from telegram import Update
from telegram.ext import CallbackContext
import whisper

# Set up logging
logger = logging.getLogger(__name__)

# Initialize Whisper model
# Using a smaller model by default for better performance on typical hardware
# Options include: "tiny", "base", "small", "medium", "large"
MODEL_SIZE = "small"
model = None  # Will be lazily loaded on first use

def load_model():
    """
    Lazily load the Whisper model.
    
    Returns:
        whisper.Model: Loaded Whisper model
    """
    global model
    if model is None:
        logger.info(f"Loading Whisper {MODEL_SIZE} model...")
        model = whisper.load_model(MODEL_SIZE)
        logger.info("Whisper model loaded successfully")
    return model

def convert_audio(file_path):
    """
    Convert Telegram audio formats to WAV format for transcription.
    
    Args:
        file_path (str): Path to the audio file to convert
        
    Returns:
        str: Path to the converted WAV file
    """
    output_path = file_path + ".wav"
    audio = AudioSegment.from_file(file_path)
    audio.export(output_path, format="wav")
    return output_path

def transcribe_audio(file_path):
    """
    Transcribe audio file using locally running Whisper model.
    
    Args:
        file_path (str): Path to the audio file to transcribe
        
    Returns:
        str: Transcribed text from the audio file
    """
    try:
        whisper_model = load_model()
        
        # Transcribe with auto language detection (will detect English or Ukrainian)
        result = whisper_model.transcribe(
            file_path,
            language=None,  # Auto-detect language
            task="transcribe",
            fp16=False  # Set to True if you have a GPU with FP16 support
        )
        
        # Return the transcribed text
        return result["text"].strip()
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return ""

async def handle_voice(update: Update, context: CallbackContext):
    """
    Handle voice messages and video notes from Telegram.
    
    Args:
        update (Update): Telegram update object
        context (CallbackContext): Telegram context object
    """
    # Check for voice, audio, or video note (circle video)
    voice = update.message.voice or update.message.audio
    video_note = update.message.video_note
    
    if not voice and not video_note:
        return

    try:
        # Create downloads directory if it doesn't exist
        os.makedirs("downloads", exist_ok=True)
        
        # Download the audio or video note file
        if voice:
            file = await context.bot.get_file(voice.file_id)
            file_path = f"downloads/{file.file_id}.ogg"
            file_type = "voice"
        else:  # video_note
            file = await context.bot.get_file(video_note.file_id)
            file_path = f"downloads/{file.file_id}.mp4"
            file_type = "video_note"
            
        await file.download_to_drive(file_path)

        # Convert and transcribe
        wav_path = convert_audio(file_path)
        
        # Send typing action while transcribing
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )
        
        transcription = transcribe_audio(wav_path)

        if transcription:
            await update.message.reply_text(f"Transcription:\n{transcription}")
        else:
            await update.message.reply_text("Sorry, I couldn't transcribe the audio.")

        # Clean up files
        try:
            os.remove(file_path)
            os.remove(wav_path)
        except Exception as cleanup_error:
            logger.warning(f"Error cleaning up files: {cleanup_error}")
            
    except Exception as e:
        error_message = f"Error processing {'video note' if 'video_note' in locals() and video_note else 'voice message'}: {str(e)}"
        logger.error(error_message)
        await update.message.reply_text(f"Sorry, there was an error processing your {'video note' if 'video_note' in locals() and video_note else 'voice message'}.")

def setup_voice_handlers(application):
    """
    Set up the voice message and video note handler in the application.
    
    Args:
        application: Telegram application object
        
    Returns:
        None
    """
    from telegram.ext import MessageHandler, filters
    
    # Register the voice message and video note handler
    application.add_handler(MessageHandler(
        filters.VOICE | filters.AUDIO | filters.VIDEO_NOTE, 
        handle_voice
    ))
    
    logger.info("Voice message and video note handlers registered")