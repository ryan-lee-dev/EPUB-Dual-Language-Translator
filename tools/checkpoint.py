from tqdm.asyncio import tqdm
from bs4 import BeautifulSoup
from pathlib import Path
from .epub_utils import EpubTool

import os
import json
import logging
import xml.etree.ElementTree as ET
import json, os, math
import shutil
import asyncio

logger = logging.getLogger(__name__)


class EpubParser:
    @staticmethod
    def get_spine_files(extract_dir, is_chapter):
        """解析 EPUB，获取阅读顺序中的正文文件（优先 toc.ncx，其次 spine）"""
        # 1. container.xml 找到 OPF 文件路径
        container_path = os.path.join(extract_dir, "META-INF", "container.xml")
        tree = ET.parse(container_path)
        root = tree.getroot()
        opf_path = root.find(
            ".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile"
        ).get("full-path")

        opf_full_path = os.path.join(extract_dir, opf_path)
        opf_dir = os.path.dirname(opf_full_path)

        # 2. 解析 OPF
        tree = ET.parse(opf_full_path)
        root = tree.getroot()

        manifest = {}
        ncx_path = None
        for item in root.findall(".//{http://www.idpf.org/2007/opf}item"):
            id_, href, media_type = (
                item.get("id"),
                item.get("href"),
                item.get("media-type"),
            )
            manifest[id_] = href
            if media_type == "application/x-dtbncx+xml":
                ncx_path = os.path.join(opf_dir, href)

        # 3. 如果有 ncx，优先解析 navMap
        if ncx_path and os.path.exists(ncx_path):
            return EpubParser._parse_ncx(ncx_path, opf_dir, is_chapter)

        # 4. 否则，回退到 spine
        logger.info("未找到 toc.ncx，回退到 spine")
        tqdm.write("未找到 toc.ncx，回退到 spine")
        spine_files = []
        for itemref in root.findall(".//{http://www.idpf.org/2007/opf}itemref"):
            idref = itemref.get("idref")
            if idref in manifest:
                href = manifest[idref]
                spine_files.append(os.path.normpath(os.path.join(opf_dir, href)))
        return spine_files

    @staticmethod
    def _parse_ncx(ncx_path, opf_dir, is_chapter):
        """解析 toc.ncx 获取正文文件列表"""
        tree = ET.parse(ncx_path)
        root = tree.getroot()
        ns = {"ncx": "http://www.daisy.org/z3986/2005/ncx/"}

        files = []
        for navpoint in root.findall(".//ncx:navPoint", ns):
            content = navpoint.find("ncx:content", ns)
            if content is not None:
                src = content.get("src")
                if (src and is_chapter(src)):
                    file_path = src.split("#")[0]  # 去掉锚点
                    abs_path = os.path.normpath(os.path.join(opf_dir, file_path))
                    if abs_path not in files:
                        files.append(abs_path)
        logger.info(f"toc.ncx 提取正文文件数: {len(files)}")
        return files


class Checkpoint:
    def __init__(self, epub_path, force=False, translate_apis=[]):
        self.epub_path = epub_path
        self.output_dir = os.path.dirname(self.epub_path)
        self.file_name: str = os.path.basename(self.epub_path)
        self.extract_dir: str = os.path.join(self.output_dir, "tmp", self.file_name.split(".")[0].replace(" ",''))
        self.force = force
        self.data = {"files": {}}
        self.checkpoint_file = f"{self.epub_path}.json"
        self.lock = asyncio.Lock()
        self.translate_apis = translate_apis
        if os.path.exists(self.checkpoint_file) and not self.force:
            self.load()
        else:
            self.init_checkpoint()
    
    def is_chapter(self, title):
        return "ch" in title.lower() or self.force
    
    def load(self):
        with open(self.checkpoint_file, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        logger.info(f"已加载检查点: [{self.checkpoint_file}]，任务继续！")

    def save(self):
        with open(self.checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        logger.info(f"检查点已保存: {self.checkpoint_file}")
        tqdm.write(f"检查点已保存: {self.checkpoint_file}")

    def init_checkpoint(self):

        if self.force:
            logger.warning(f"强制清空缓存:{self.extract_dir}!")
            tqdm.write(f"强制清空缓存:{self.extract_dir}!")
            
            logger.warning(f"强制清空进度:{self.checkpoint_file}!")
            tqdm.write(f"强制清空进度:{self.checkpoint_file}!")
            
            shutil.rmtree(self.extract_dir, ignore_errors=True)

            try:
                os.remove(self.checkpoint_file)
            except FileNotFoundError:
                pass

        if os.path.exists(self.checkpoint_file):
            self.load()
            return

        EpubTool.extract(self.epub_path, self.extract_dir)

        html_files = EpubParser.get_spine_files(self.extract_dir, self.is_chapter)
        for f in html_files:
            self.data["files"][f] = False
        self.save()

    def get_next_file(self):
        for _, entry in enumerate(self.data["files"]):
            yield entry

    def complete_chapter(self, file_path):
        self.data["files"][file_path] = True
        self.save()

    async def load_chapter_process(self, file_path):
        # 不存在则创建，存在则加载，前提是对应的epub文件存在

        p_tags = []
        if not os.path.exists(file_path):
            tqdm.write(f"{file_path} not exist!")
            return None, None

        with open(file_path, "r", encoding="utf-8") as fp:
            soup = BeautifulSoup(fp, "html.parser")
            for p in soup.find_all("p"):
                if "__trans__" in p.get("class", []):
                    tqdm.write(f"{file_path} 已翻译完成，跳过！")
                    return None, None

                if len(p.get_text(strip=True)) > 1:
                    p_tags.append(p)

        file_name = os.path.basename(file_path)
        cp_data_path = os.path.join(self.extract_dir, f"{file_name}.cp_data")

        if os.path.exists(cp_data_path):
            with open(cp_data_path, "r", encoding="utf-8") as f:
                return json.load(f), p_tags

        progress = {}
        for idx in range(len(p_tags)):
            progress[str(idx)] = ""

        with open(cp_data_path, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)

        return progress, p_tags

    async def update_chapter_process(self, file_path, idx, translated_text):
        file_name = os.path.basename(file_path)
        cp_data_path = os.path.join(self.extract_dir, f"{file_name}.cp_data")

        if not os.path.exists(cp_data_path):
            logger.error(f"{file_name} 进度异常！")
            exit(1)

        async with self.lock:
            progress = {}
            if os.path.exists(cp_data_path):
                with open(cp_data_path, "r", encoding="utf-8") as f:
                    progress = json.load(f)

            progress[str(idx)] = translated_text

            with open(cp_data_path, "w", encoding="utf-8") as f:
                json.dump(progress, f, ensure_ascii=False, indent=2)

    async def do_trans(
        self, start, end, p_tags, progress, file_path, translate_ai, position
    ):
        if start >= end:
            return

        for i in tqdm(
            range(start, end),
            desc=os.path.basename(file_path)[:10] + f"[{start:03}:{end:03}]",
            position=position,
            ncols=80,
            leave=True,
        ):
            try:
                if len(progress.get(str(i), "")) != 0:
                    continue

                text = str(p_tags[i])
                translated_text = await translate_ai(text)
                await self.update_chapter_process(file_path, i, translated_text)
            except KeyboardInterrupt as e:
                tqdm.write(f"\n用户手动终止！")
                exit(1)

    async def apply_progress_to_file(self, file_path):

        progress, _ = await self.load_chapter_process(file_path)

        if len(progress) < 1 or progress is None:
            logger.warning(f"{file_path}无内容！")
            return False

        if not os.path.exists(file_path):
            logger.error(f"{file_path} 目标文件不存在")
            return False

        p_tags = []

        with open(file_path, "r", encoding="utf-8") as fp:
            soup = BeautifulSoup(fp, "html.parser")
            for p in soup.find_all("p"):
                if "__trans__" in p.get("class", []):
                    tqdm.write(f"{file_path} 已翻译完成，跳过！")
                    return False

                if len(p.get_text(strip=True)) > 1:
                    p_tags.append(p)

        logging.info(f"应用 progress 更新 {file_path}, 共 {len(progress)} 条翻译")
        for idx_str, translated in progress.items():
            idx = int(idx_str)
            if idx < 0 or idx >= len(p_tags):
                logging.warning(f"索引 {idx} 超出范围，跳过")
                continue

            if not translated.strip():
                logging.warning(f"progress[{idx}] 无翻译内容，跳过")
                continue

            # 创建 <div class="trans"> 包裹翻译内容
            trans_div = soup.new_tag("p", **{"class": "__trans__"})
            frag = BeautifulSoup(translated, "html.parser")
            trans_div.append(frag)

            # 插入到原 p 标签之后
            p_tags[idx].insert_after(trans_div)

        # 写入备份文件
        Path(f"{file_path}.bak").write_text(str(soup), encoding="utf-8")
        logging.info(f"{file_path}.bak 已更新")
        return True

    async def translate_epub(self, file_path, task_num):
        self.load()
        files = self.data.get("files", [])
        if len(files) == 0:
            return

        if self.data["files"].get(file_path, True):
            logger.info(f"{file_path}已翻译。")
            return

        progress, p_tags = await self.load_chapter_process(file_path)

        if progress is None or p_tags is None:
            logger.warning(f"{file_path}内容异常（不存在或者已翻译）！")
            self.complete_chapter(file_path)
            return

        total = len(p_tags)
        if len(progress) < 1 or total < 1:
            logger.warning(f"{file_path}无内容！")
            return

        chunk_size = math.ceil(total / task_num)

        tasks = []
        for t in range(task_num):
            start = t * chunk_size
            end = min((t + 1) * chunk_size, total)
            tasks.append(
                asyncio.create_task(
                    self.do_trans(
                        start,
                        end,
                        p_tags,
                        progress,
                        file_path,
                        self.translate_apis[0],
                        t,
                    )
                )
            )

        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(e)
            tqdm.write(f"处理:{file_path}出现错误，已跳过")
            return
        except KeyboardInterrupt:
            logger.warning("任务终止：用户手动停止")
            tqdm.write("任务终止：用户手动停止")
            exit(1)

        # 翻译失败只保存进度，不应用翻译，保证源文件的纯净
        is_ok = await self.apply_progress_to_file(file_path)
        if is_ok:
            self.complete_chapter(file_path)
            shutil.move(f"{file_path}.bak", file_path)
            tqdm.write(f"{file_path} 翻译完成！")
        else:
            tqdm.write(f"{file_path} 翻译失败！")
            logger.warning(f"{file_path}，翻译失败！")
