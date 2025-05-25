from typing import Optional
import logging

logging.basicConfig(
    level=logging.INFO,  # or DEBUG
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

def read_file(path: str) -> Optional[str]:
    try:
        with open(path, 'r', encoding='utf-8') as file:
            content: str = file.read()
        return content
    except FileNotFoundError:
        logger.info(f"File not found: {path}")
        return None
    except Exception as e:
        logger.info(f"Error reading file: {e}")
        return None


def write_to_file(path: str, content: str) -> None:
    try:
        with open(path, 'a', encoding='utf-8') as file:
            file.write(content)
        logger.info(f"Content written to file: {path}")
    except FileNotFoundError:
        logger.error(f"File not found: {path}")
        raise
    except Exception as e:
        logger.error(f"Error writing to file '{path}': {e}")
        raise
