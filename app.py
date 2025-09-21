from fastapi import FastAPI, Query , HTTPException
from fastapi.responses import StreamingResponse
import subprocess
import urllib

app = FastAPI()

@app.get("/extract-audio")
async def extract_audio(video_url: str = Query(..., description="Encoded video URL")):
    decoded_url = urllib.parse.unquote(video_url)
    # ffmpeg command    
    print(decoded_url)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "debug",
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

@app.get("/download-audio")
async def download_audio(video_url: str = Query(..., description="Encoded video URL")):
    decoded_url = urllib.parse.unquote(video_url.strip())
    
    # ffmpeg command to extract audio to stdout
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",          # hide verbose logs
        "-headers", "User-Agent: Mozilla/5.0",
        "-i", decoded_url,
        "-vn",                         # no video
        "-acodec", "libmp3lame",
        "-ar", "44100",
        "-ac", "2",
        "-b:a", "192k",
        "-f", "mp3",
        "pipe:1"                       # send to stdout
    ]
    
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        def iter_file():
            try:
                while True:
                    chunk = process.stdout.read(1024 * 400)  # 64 KB chunks
                    if not chunk:
                        break
                    yield chunk
            finally:
                process.stdout.close()
                process.stderr.close()
                process.kill()

        headers = {
            "Content-Disposition": "attachment; filename=audio.mp3"
        }

        return StreamingResponse(iter_file(), media_type="audio/mpeg", headers=headers)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio download failed: {str(e)}")