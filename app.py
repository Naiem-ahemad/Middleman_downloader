from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
import subprocess
import urllib

app = FastAPI()

@app.get("/extract-audio")
async def extract_audio(video_url: str = Query(..., description="Encoded video URL")):
    decoded_url = urllib.parse.unquote(video_url)
    # ffmpeg command    
    command = [
        "ffmpeg",
        "-hide_banner",
        "-headers", "User-Agent: Mozilla/5.0",
        "-i", decoded_url.strip(),   # <-- keep entire URL as one arg
        "-vn",
        "-acodec", "libmp3lame",
        "-ar", "44100",
        "-ac", "2",
        "-b:a", "192k",
        "-f", "mp3",
        "pipe:1"
    ]

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    return StreamingResponse(process.stdout, media_type="audio/mpeg")
