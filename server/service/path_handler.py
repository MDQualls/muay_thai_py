from datetime import datetime
from pathlib import Path

class PathHandler:

    @staticmethod
    def make_output_path(fighter_name: str, slide_num: int) -> Path:
        """Generate a timestamped output path for a carousel slide JPEG.

        Args:
            fighter_name: Fighter's full name e.g. "Rodtang Jitmuangnon"
            slide_num: Slide number 1, 2, or 3

        Returns:
            Path e.g. "output/rodtang_jitmuangnon_20240101_120000_slide1.jpg"
        """
        slug = fighter_name.lower().replace(" ", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return Path("output") / f"{slug}_{timestamp}_slide{slide_num}.jpg"
