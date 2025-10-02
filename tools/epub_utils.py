import zipfile
import os
import shutil
import logging
from tqdm import tqdm

logger = logging.getLogger(__name__)

class EpubTool:
    @staticmethod
    def extract(epub_path, extract_to, clean=False):
        if os.path.exists(extract_to) and not os.path.isdir(extract_to):
            logger.error(f"目标位置已存在文件: {extract_to}")
            return
        
        if clean and os.path.exists(extract_to):
            shutil.rmtree(extract_to)
            logger.warning(f"清空目录: {extract_to}")

        if not clean and os.path.exists(extract_to):
            logger.warning(f"继续上一次的任务: {extract_to}")
            return
        
        os.makedirs(extract_to, exist_ok=True)

        with zipfile.ZipFile(epub_path, 'r') as zf:
            zf.extractall(extract_to)

        tqdm.write(f"解压完成: {extract_to}")

    @staticmethod
    def package_epub(cp , clean=False):
        output_name = os.path.join(cp.extract_dir, '..', '..', f"bi_{cp.file_name}")

        with zipfile.ZipFile(output_name, 'w') as zf:
            mimetype_path = os.path.join(cp.extract_dir, "mimetype")
            if os.path.exists(mimetype_path):
                zf.write(mimetype_path, "mimetype", compress_type=zipfile.ZIP_STORED)

            for root, _, files in os.walk(cp.extract_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, cp.extract_dir)

                    if rel_path == "mimetype":
                        continue
                    if file.endswith(".cp_data"):
                        continue
                    
                    if file.endswith(".epub"):
                        continue
                    
                    zf.write(file_path, rel_path, compress_type=zipfile.ZIP_DEFLATED)

        tqdm.write(f"EPUB 打包完成: {output_name}\n")

        if clean:
            shutil.rmtree(cp.extract_dir)
            logger.warning(f"清空目录: {cp.extract_dir}")