import logging

logger = logging.getLogger("dr3.reverse_image")

class ReverseImageEngine:
    """Generates reverse image search links for avatars."""
    
    @staticmethod
    def get_reverse_search_links(image_url: str) -> dict:
        if not image_url or image_url.endswith("default_profile_normal.png"):
            return {}
            
        return {
            "Google Lens": f"https://lens.google.com/uploadbyurl?url={image_url}",
            "TinEye": f"https://tineye.com/search?url={image_url}",
            "Yandex": f"https://yandex.com/images/search?rpt=imageview&url={image_url}"
        }
