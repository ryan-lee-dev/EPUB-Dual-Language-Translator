from abc import ABC, abstractmethod
import asyncio

prompt = """你是一个专业的书籍翻译助手，你要完成给定文字->翻译文字的任务。
任务(顺序决定优先级)：
1. 将以下 HTML 段落中的文本翻译成中文，必须保留所有 HTML 标签不变，注重于原意。
2. 特殊的英文名词，人名，专有名词，代码片段，头文件等内容，不进行翻译。
3. 符合人类阅读习惯，包括合理的上下文连贯，语法，标点符号等。
4. 这是一本计算机技术相关书籍，需要稍微润色一下(20%)，但是要注重于原意。
5. class = programlisting 的段落不要进行翻译。

注意事项（严格遵循）：
1. 你的翻译将会最终输出到书籍中，不允许给出任何无关说明或者非原文的内容。

样例：
输入：<p>This is a <b>book</b> <code>tools</code>.</p>

输出：<p>这是一本 <b>书</b><code>tools</code>。</p>

输入:<p class="programlisting">$ git pull</p>
输出:<br/>

"""


class AITranslator(ABC):
    @abstractmethod
    async def __call__(self, text: str) -> str:
        pass


class FooAITranslator(AITranslator):
    async def __call__(self, text: str) -> str:
        await asyncio.sleep(0.2)
        return f"""<span style="color: red;">foo:</span> {text}"""
