import re
from flask import Flask, request, render_template, jsonify
from werkzeug.utils import secure_filename
import openai
import json
import os
from PyPDF2 import PdfReader
from docx import Document
from config import baseurl,api_key

app = Flask(__name__)
app.json.ensure_ascii =False;
# 配置
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SUMMARY_FILE'] = 'summaries.json'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'docx', 'txt'}
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB
# 初始化 OpenAI 客户端（适配 DashScope）
client = openai.OpenAI(api_key=api_key, base_url=baseurl)
# 模型名称（Qwen3）
model_name = "qwen3-235b-a22b"

# 创建上传目录
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def read_file_content(file_path):
    ext = file_path.split('.')[-1].lower()

    if ext == 'pdf':
        reader = PdfReader(file_path)
        return ' '.join(page.extract_text() for page in reader.pages if page.extract_text())
    elif ext == 'docx':
        doc = Document(file_path)
        return ' '.join(paragraph.text for paragraph in doc.paragraphs)
    elif ext == 'txt':
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""


def truncate_content(content, max_chars=8000):
    if len(content) > max_chars:
        return content[:max_chars] + "..."
    return content


def ai_split_text(content):
    """
    使用 AI 对文本进行语义切分
    :param content: 原始文本
    :return: chunk 列表
    """
    prompt = f"""
你是一个专业的文本分析助手，请根据以下要求处理输入的文档内容：

请仔细阅读下面的文本，并按照**自然语义单元**将其划分为多个部分。
每个部分应满足：
1. 包含一个完整的意思或主题
2. 不跨句切断
3. 每个部分长度控制在 1000 字以内
4. 输出格式为 JSON 列表，每项包含 "chunk_id" 和 "content"
5. 必须把所有的文章全部分割，不准偷懒

输出格式如下：
[
  {{
    "chunk_id": 0,
    "content": "第一部分内容"
  }},
  {{
    "chunk_id": 1,
    "content": "第二部分内容"
  }}
]

以下是你要处理的文本：
{content}
"""
    print(prompt)
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "你是一个专业的内容解析器，严格按照 JSON 格式返回结果"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            # max_tokens=2000,
            stream=True
        )

        full_response = ""
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                full_response += chunk.choices[0].delta.content

        json_match = re.search(r'\[.*\]', full_response, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            chunks = json.loads(json_str.strip())
        return chunks
        # 尝试解析 JSON
        

    except Exception as e:
        raise Exception(f"AI 文本切分失败: {str(e)}")


def generate_summary_for_chunks(chunk_texts):
    summaries = []
    for idx, chunk in enumerate(chunk_texts):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "请为以下文本生成简明摘要（约50字）："},
                    {"role": "user", "content": truncate_content(chunk, 4000)}
                ],
                temperature=0.7,
                max_tokens=100,
                stream=True
            )

            full_response = ""
            for chunk_resp in response:
                if chunk_resp.choices and chunk_resp.choices[0].delta.content:
                    full_response += chunk_resp.choices[0].delta.content

            summaries.append({
                "summary": full_response.strip()
            })

        except Exception as e:
            print(f"第 {idx} 个 chunk 摘要生成失败: {e}")
            summaries.append({
                "summary": "[摘要生成失败]"
            })
    return summaries


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "未检测到文件"}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"error": "未选择文件"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        try:
            file.save(file_path)
            content = read_file_content(file_path)

            if not content:
                os.remove(file_path)
                return jsonify({"error": "文件内容为空，无法生成摘要"}), 400

            # 使用 AI 进行语义切分
            chunks = ai_split_text(content)
            os.makedirs(f"{file.filename}")
            for i in chunks:
                chunk_id = i["chunk_id"]
                with open(f"{file.filename}/{chunk_id}.txt","w+",encoding="utf-8") as f:
                    f.write(i["content"])
            # 提取所有 chunk 的内容用于生成摘要
            chunk_contents = [c["content"] for c in chunks]

            # 为每个 chunk 生成摘要
            summarized_chunks = generate_summary_for_chunks(chunk_contents)

            # 合并 chunk 内容和摘要
            final_chunks = []
            for i, chunk in enumerate(chunks):
                final_chunks.append({
                    "chunk_id": chunk.get("chunk_id", i),
                    "content": chunk["content"],
                    "summary": summarized_chunks[i]["summary"]
                })

            # 存储到 summaries.json
            summaries = {}
            if os.path.exists(app.config['SUMMARY_FILE']):
                with open(app.config['SUMMARY_FILE'], 'r', encoding='utf-8') as f:
                    try:
                        summaries = json.load(f)
                    except json.JSONDecodeError:
                        summaries = {}

            summaries[filename] = final_chunks

            with open(app.config['SUMMARY_FILE'], 'w', encoding='utf-8') as f:
                json.dump(summaries, f, ensure_ascii=False, indent=2)

            return jsonify({
                "filename": filename,
                "chunk_count": len(final_chunks),
                "message": "文件上传成功并由 AI 完成分块与摘要"
            })

        except Exception as e:
            if os.path.exists(file_path):
                os.remove(file_path)
            return jsonify({"error": str(e)}), 500

    return jsonify({"error": "文件类型不支持"}), 400


@app.route('/ask', methods=['POST'])
def ask_question():
    data = request.get_json()
    question = data.get('question')

    if not question:
        return jsonify({"error": "未提供问题"}), 400

    try:
        # 检查是否存在摘要文件
        if not os.path.exists(app.config['SUMMARY_FILE']):
            return jsonify({"error": "未找到摘要文件，请先上传文件生成摘要"}), 404

        with open(app.config['SUMMARY_FILE'], 'r', encoding='utf-8') as f:
            all_summaries = json.load(f)

        if not all_summaries:
            return jsonify({"error": "摘要文件为空，请先上传文件生成摘要"}), 404

        # 构建上下文：所有 chunk 的摘要
        context = ""
        for filename, chunks in all_summaries.items():
            for chunk in chunks:
                context += f"文件名: {filename}\n摘要: {chunk['summary']}\n\n"

        # 步骤一：让 AI 找到最相关的文件
        prompt_relevant_file = f"""根据以下问题判断最相关的文件：
问题: {question}

文件摘要列表:
{context}

请返回最相关的文件名（如果没有相关文件，请返回"无相关文件"），不要包含其他信息，直接输出文件名。"""

        response_relevant_file = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt_relevant_file}],
            temperature=0.1,
            max_tokens=50,
            stream=True
        )

        relevant_file = ""
        for chunk in response_relevant_file:
            if chunk.choices and chunk.choices[0].delta.content:
                relevant_file += chunk.choices[0].delta.content.strip()
        relevant_file = relevant_file.strip()

        if relevant_file == "无相关文件" or relevant_file not in all_summaries:
            return jsonify({
                "answer": "未找到相关文件或文件内容。",
                "relevant_file": None
            })

        # 步骤二：在匹配的文件中找最相关的 chunk
        matched_chunks = all_summaries[relevant_file]
        chunk_context = ""
        for c in matched_chunks:
            chunk_context += f"Chunk ID: {c['chunk_id']}\n摘要: {c['summary']}\n\n"

        prompt_relevant_chunk = f"""根据以下问题判断最相关的段落编号（chunk_id）：
问题: {question}

段落摘要列表:
{chunk_context}

请只返回一个数字（chunk_id）。如果没有相关段落，请返回 -1。"""

        response_relevant_chunk = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt_relevant_chunk}],
            temperature=0.1,
            max_tokens=10,
            stream=True
        )

        relevant_chunk_id = -1
        chunk_response = ""
        for chunk in response_relevant_chunk:
            if chunk.choices and chunk.choices[0].delta.content:
                chunk_response += chunk.choices[0].delta.content.strip()
        try:
            relevant_chunk_id = int(chunk_response.strip())
        except:
            relevant_chunk_id = -1

        if relevant_chunk_id < 0 or relevant_chunk_id >= len(matched_chunks):
            return jsonify({
                "answer": "未找到相关段落。",
                "relevant_file": relevant_file,
                "relevant_chunk_id": -1
            })

        # 步骤三：获取原始文件中的完整内容
        file_path = matched_chunks[0].get("file_path")
        if not file_path or not os.path.exists(file_path):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], relevant_file)

        full_text = read_file_content(file_path)
        selected_chunk = matched_chunks[relevant_chunk_id]["content"]

        # 步骤四：调用 AI 根据 chunk 内容回答问题
        answer_prompt = f"""你是一个基于文档内容的问答助手。请根据以下段落回答问题。
如果段落中没有相关信息，请说明。

段落内容:
{selected_chunk}

问题:
{question}

请直接给出答案，简洁明了。"""

        answer_response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": answer_prompt}],
            temperature=0.5,
            max_tokens=500,
            stream=True
        )

        full_answer = ""
        for chunk in answer_response:
            if chunk.choices and chunk.choices[0].delta.content:
                full_answer += chunk.choices[0].delta.content

        return jsonify({
            "relevant_file": relevant_file,
            "relevant_chunk_id": relevant_chunk_id,
            "chunk_summary": matched_chunks[relevant_chunk_id]['summary'],
            "answer": full_answer.strip()
        })

    except openai.APIError as e:
        return jsonify({"error": f"OpenAI API 问答失败 (API Error): {e.response.status_code} - {e.message}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run()