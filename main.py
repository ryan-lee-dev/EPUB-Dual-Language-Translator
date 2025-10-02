from tools.checkpoint import Checkpoint
from translators.base_translator import get_translator
from tools.epub_utils import EpubTool
from tqdm import tqdm

import logging
import os, time
import asyncio
import argparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s- %(filename)s-%(funcName)s(): %(message)s",
    handlers=[
        logging.FileHandler(
            f"bi_trans_{time.strftime("%Y%m%d%H", time.localtime())}.log",
            encoding="utf-8",
        ),
    ],
)

logger = logging.getLogger(__name__)
logging.getLogger("httpx").disabled = True
logging.getLogger("openai").disabled = True


parser = argparse.ArgumentParser(description="处理 EPUB 文件")

parser.add_argument(
    "--file",
    type=str,
    required=True,
    help="要处理的 EPUB 文件路径",
)

parser.add_argument(
    "--mode",
    type=str,
    default="extract",
    help="要处理的 EPUB 文件路径",
)

parser.add_argument(
    "--ai",
    type=str,
    default="foo",
    help="使用的ai",
)

parser.add_argument(
    "--tasks",
    type=int,
    default=2,
    help="同时运行的任务数量 (默认: 2)",
)

parser.add_argument(
    "--force",
    action="store_true",
    help="强制清除上次的缓存",
)

args = parser.parse_args()

async def main():
    epub_path = args.file

    if len(epub_path) < 1 or not os.path.exists(epub_path):
        tqdm.write(f"epub book:[{epub_path}] not exist!")
        exit(1)

    tasks = args.tasks
    ai = args.ai
    mode = args.mode
    force = args.force
    tqdm.write(f"Now running on {mode}!")
    match mode:
        case "trans":
            pass

        case "package":
            cp = Checkpoint(epub_path)
            EpubTool.package_epub(cp)
            exit(0)
        case "extract":
            Checkpoint(epub_path, force)
            exit(0)
    tqdm.write(f"使用:[{ai}]\n处理：{epub_path}\n并行运行: {tasks}个任务！")

    translator = [get_translator(ai)]
    cp = Checkpoint(epub_path, args.force, translator)

    for file_path in cp.get_next_file():
        if not os.path.exists(file_path):
            tqdm.write(f"{file_path} 不存在！")
            break
        await cp.translate_epub(file_path, tasks)

    EpubTool.package_epub(cp)


if __name__ == "__main__":
    asyncio.run(main())
