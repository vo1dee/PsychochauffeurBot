import aiohttp
import asyncio
import re
import json
import os
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
from modules.logger import error_logger

class ImageDownloader:
    INSTAGRAM_REGEX = re.compile(r"(https?://(?:www\.)?instagram\.com/p/[^/?#&]+)")
    TIKTOK_REGEX = re.compile(r"(https?://(?:www\.)?tiktok\.com/@[^/?#]+/video/\d+)")

    def __init__(self) -> None:
        pass

    async def fetch_instagram_images(self, url: str) -> List[str]:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            }
            
            results = []
            
            async with aiohttp.ClientSession() as session:
                # Try JSON endpoint first
                try:
                    async with session.get(url + "?__a=1&__d=dis", headers=headers) as resp:
                        error_logger.error(f"[ImageDL] Response Content-Type: {resp.headers.get('Content-Type')}")  # Log content type
                        if resp.status == 200 and 'application/json' in resp.headers.get('Content-Type', ''):
                            data = await resp.json()
                            error_logger.error(f"[ImageDL] Full Instagram JSON Response: {json.dumps(data, indent=2)}")

                            images = self._parse_instagram_json(data)
                            if images:
                                results.extend(images)

                except Exception as e:
                    error_logger.error(f"[ImageDL] IG JSON endpoint error: {e}")
                    error_logger.error(f"[ImageDL] URL failed: {url + '?__a=1&__d=dis'}")
                
                # Always do HTML scraping as well to ensure we get images
                try:
                    async with session.get(url, headers=headers) as resp2:
                        html = await resp2.text()
                        html_images = self._parse_instagram_html(html)
                        results.extend(html_images)
                except Exception as e:
                    error_logger.error(f"[ImageDL] IG HTML scraping error: {e}")
                    error_logger.error(f"[ImageDL] URL failed: {url}")
            
            # Remove duplicates while preserving order
            unique_results = []
            seen = set()
            for img in results:
                if img not in seen:
                    seen.add(img)
                    unique_results.append(img)
            
            error_logger.error(f"[ImageDL] Found {len(unique_results)} images.")  # Debug found images
            return unique_results

        except Exception as e:
            error_logger.error(f"[ImageDL] IG fetch error for {url}: {e}")
            return []


    def _parse_instagram_json(self, data: Dict[str, Any]) -> List[str]:
        try:
            results: List[str] = []
            media = data.get("items") or data.get("graphql", {}).get("shortcode_media")
            
            error_logger.error(f"[ImageDL] Parsed JSON media: {json.dumps(media, indent=2)}")  # Log media data

            if isinstance(media, list):
                media = media[0]
            if not media:
                return results

            def is_uncropped(url: str) -> bool:
                return "s640x640" not in url and "stp=" not in url

            def get_best_resource(resources: Any) -> Optional[str]:
                if not isinstance(resources, list):
                    return None
                sorted_res = sorted(resources, key=lambda r: r.get("config_width", 0), reverse=True)
                for res in sorted_res:
                    url = res.get("src")
                    if url and is_uncropped(url) and isinstance(url, str):
                        return str(url)
                first_url = sorted_res[0].get("src") if sorted_res else None
                return first_url if isinstance(first_url, str) else None

            # Carousel post
            edges = media.get("edge_sidecar_to_children", {}).get("edges")
            if edges:
                for edge in edges:
                    node = edge.get("node", {})
                    disp_res = node.get("display_resources")
                    url = get_best_resource(disp_res)
                    if url:
                        results.append(url)
                    else:
                        fallback = node.get("display_url")
                        if fallback:
                            results.append(fallback)
            else:
                # Single image post
                disp_res = media.get("display_resources")
                url = get_best_resource(disp_res)
                if url:
                    results.append(url)
                else:
                    fallback = media.get("display_url")
                    if fallback:
                        results.append(fallback)

            error_logger.error(f"[ImageDL] JSON parsed results: {results}")  # Debug parsed results
            return results

        except Exception as e:
            error_logger.error(f"[ImageDL] IG JSON parse error: {e}")
            return []



    
    def _parse_instagram_html(self, html: str) -> List[str]:
        try:
            soup = BeautifulSoup(html, 'html.parser')
            imgs = []
            
            # First try to extract from JSON data in scripts
            found_in_scripts = False
            scripts = soup.find_all('script', type="text/javascript")
            
            for script in scripts:
                if not script.string:
                    continue
                    
                # Look for image URLs directly in script contents
                if 'display_url' in script.string:
                    matches = re.findall(r'"display_url":"([^"]+)"', script.string)
                    for match in matches:
                        url = match.replace('\\u0026', '&').replace('\\/', '/')
                        imgs.append(url)
                        found_in_scripts = True
                        
                # Try to extract from window._sharedData
                if 'window._sharedData' in script.string:
                    try:
                        json_str = re.search(r'window\._sharedData\s*=\s*({.+?});</script>', script.string, re.DOTALL)
                        if json_str:
                            json_data = json.loads(json_str.group(1))
                            post_data = json_data.get('entry_data', {}).get('PostPage', [{}])[0]
                            media = post_data.get('graphql', {}).get('shortcode_media', {})
                            
                            # Get display_url
                            display_url = media.get('display_url')
                            if display_url:
                                imgs.append(display_url)
                                found_in_scripts = True
                                
                            # Get from carousel
                            edges = media.get('edge_sidecar_to_children', {}).get('edges', [])
                            for edge in edges:
                                node_url = edge.get('node', {}).get('display_url')
                                if node_url:
                                    imgs.append(node_url)
                                    found_in_scripts = True
                    except Exception as e:
                        error_logger.error(f"[ImageDL] Error parsing window._sharedData: {e}")
            
            # If nothing found in scripts, use meta tags (may be cropped but better than nothing)
            if not found_in_scripts:
                ogs = soup.find_all('meta', property='og:image')
                for tag in ogs:
                    if tag.has_attr('content'):
                        imgs.append(tag['content'])
                        
                # Also look for content URLs
                content_tags = soup.find_all('meta', property='og:image:url')
                for tag in content_tags:
                    if tag.has_attr('content'):
                        imgs.append(tag['content'])
            
            error_logger.error(f"[ImageDL] Parsed images: {imgs}")  # Debug the images found
            return imgs
            
        except Exception as e:
            error_logger.error(f"[ImageDL] IG HTML parse error: {e}")
            return []


    async def fetch_tiktok_image(self, url: str) -> List[str]:
        """
        Extracts cover image of TikTok video page.
        """
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            async with aiohttp.ClientSession() as s:
                async with s.get(url, headers=headers) as r:
                    text = await r.text()
                    soup = BeautifulSoup(text, 'html.parser')
                    og = soup.find("meta", property="og:image")
                    if og and hasattr(og, 'has_attr') and og.has_attr('content') and hasattr(og, 'get'):
                        content = og.get('content')
                        if content and hasattr(content, 'string'):
                            return [str(content)]
                        elif isinstance(content, str):
                            return [content]
                    
                    m = re.search(r'"cover":"([^"]+)"', text)
                    if m: 
                        img = m.group(1).replace('\\u0026', '&')
                        return [img]
                    
        except Exception as e:
            error_logger.error(f"[ImageDL] TikTok fetch fail for {url}: {e}")
            
        return []

    async def download_images_from_urls(self, image_urls: List[str], path: str = "downloads") -> List[str]:
        # Allow only valid images (i.e., without the cropped pattern)
        image_urls = [url for url in image_urls if not ("s640x640" in url or "stp=" in url or "e35" in url)]

        if not image_urls:
            error_logger.error("[ImageDL] No image URLs provided for download")
            return []
        
        saved_files: List[str] = []
        
        os.makedirs(path, exist_ok=True)

        async with aiohttp.ClientSession() as s:
            tasks = []
            
            for idx, imgurl in enumerate(image_urls):
                task_name = getattr(asyncio.current_task(), 'get_name', lambda: 'task')()
                filename = os.path.join(path, f"image_{task_name}_{idx}.jpg")
                
                tasks.append(asyncio.create_task(
                    self._download_one_image(s, imgurl, filename, saved_files)))
            
            await asyncio.gather(*tasks)
        
        return saved_files
    
    async def _download_one_image(self, sess: aiohttp.ClientSession, imgurl: str, outfile: str, saved_list: List[str]) -> None:
        try:
            error_logger.error(f"[ImageDL] Downloading: {imgurl}")  # DEBUG
            
            async with sess.get(imgurl) as r:
                if r.status == 200:
                    with open(outfile, "wb") as f:
                        while True:
                            chunk = await r.content.read(10240)
                            if not chunk: break
                            f.write(chunk)
                    saved_list.append(outfile)
                    error_logger.error(f"[ImageDL] Downloaded successfully: {outfile}")  # DEBUG
                else:
                    error_logger.error(f"[ImageDL] Download failed HTTP{r.status} - {imgurl}")

        except Exception as e:
            error_logger.error(f"[ImageDL] Download err {imgurl}: {e}")