import os
import aiohttp
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
import asyncio

app = FastAPI()

@app.get("/")
async def root():
    """
    A simple root endpoint to explain how to use the API.
    """
    return {
        "message": "Welcome to the Video Download Proxy API!",
        "instructions": "To get a force-download link, use the '/download_video' endpoint with a 'video_url' query parameter. "
                        "Example: /download_video?video_url=https://storage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
    }

@app.get("/download_video")
async def download_video(video_url: str, request: Request):
    """
    This endpoint acts as a proxy, streaming a video from a source URL to the client
    and forcing a download via HTTP headers. It supports resumable downloads and
    retries to handle network interruptions.
    
    Args:
        video_url (str): The URL of the video to be downloaded.
        request (Request): The incoming request object from the client.
    
    Returns:
        StreamingResponse: A response that streams the video content to the client.
    """
    timeout = aiohttp.ClientTimeout(total=600)  # 10 minutes timeout
    max_retries = 5
    retries = 0
    
    async def content_iterator(content_range_start=0):
        nonlocal retries
        while retries < max_retries:
            try:
                headers = {}
                if content_range_start > 0:
                    headers['Range'] = f'bytes={content_range_start}-'
                
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(video_url, headers=headers) as resp:
                        if resp.status not in [200, 206]:
                            raise HTTPException(status_code=resp.status, detail=f"Could not fetch video from the provided URL. Status code: {resp.status}")
                        
                        async for chunk in resp.content.iter_any():
                            yield chunk
                            content_range_start += len(chunk)
                        return # End the generator if loop completes

            except aiohttp.client_exceptions.ClientConnectionError as e:
                retries += 1
                if retries >= max_retries:
                    raise HTTPException(status_code=500, detail=f"Failed to connect after {max_retries} retries: {e}")
                print(f"Connection closed. Retrying {retries}/{max_retries}...")
                await asyncio.sleep(2 ** retries) # Exponential backoff
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

    try:
        # Get filename and check if the source URL supports range headers
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.head(video_url) as resp:
                if 'accept-ranges' not in resp.headers:
                    print("Warning: Source server does not support 'Accept-Ranges'. Resumable downloads may not work.")
                
                filename = os.path.basename(video_url).split('?')[0]
                
                # Check for byte range requests from the client (e.g., a browser resuming a download)
                client_range_header = request.headers.get('Range')
                if client_range_header:
                    start_byte = int(client_range_header.split('=')[1].split('-')[0])
                    response_headers = {
                        "Content-Disposition": f"attachment; filename=\"{filename}\"",
                        "Accept-Ranges": "bytes",
                        "Content-Range": f"bytes {start_byte}-{resp.content_length-1}/{resp.content_length}"
                    }
                    return StreamingResponse(
                        content_iterator(content_range_start=start_byte),
                        media_type="video/mp4",
                        headers=response_headers,
                        status_code=206 # Partial Content
                    )
                
                # Default response for a new download
                return StreamingResponse(
                    content_iterator(),
                    media_type="video/mp4",
                    headers={
                        "Content-Disposition": f"attachment; filename=\"{filename}\"",
                        "Accept-Ranges": "bytes"
                    }
                )

    except aiohttp.ClientConnectorError:
        raise HTTPException(status_code=502, detail="Failed to connect to the video source.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")
