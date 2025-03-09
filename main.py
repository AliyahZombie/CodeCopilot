import os
import json
import uuid
import subprocess
from openai import OpenAI
from pathlib import Path
from colored import fg, attr
import sys

# 加载配置文件
def load_config(config_file="config.json"):
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"未找到 {config_file}，请创建配置文件")
        exit(1)
    except json.JSONDecodeError:
        print(f"{config_file} 格式错误")
        exit(1)

# 初始化配置
config = load_config()
api_key = config.get("api_key")
base_url = config.get("base_url")
model = config.get("model")

client = OpenAI(
    api_key=api_key,
    base_url=base_url  # 使用自定义 API 基址
)

# 系统消息，定义模型行为
system_message = {
    "role": "system",
    "content": f"你正运行在{sys.platform}平台\n" + """You are an AI assistant that helps users create projects. Generate project files based on user requirements and return them strictly in JSON format without any additional content (do not start with a code block structure, just provide the JSON data). You must ask the user at least once if they have further requirements before proactively marking the project as completed:
        {
        "files": [{"filename": "file1.py", "content": "file content"}],
        "message": "Message to the user (Please use user's language and briefly explain what you are doing, such as initializing the project, creating folders, etc., or provide a detailed description of your implementation)",
        "run_command": "Command to start the project (note that this command will be executed directly, determine the instruction format based on the user's platform), e.g., 'python app.py'. For front-end projects, also provide a start command (e.g., open via the user's browser). If an init command is needed, you can initially provide no files and only give the start command. If folder creation is required, provide the command first (do not create a project folder but try to output code files directly; you don’t need to ask the user for authorization, as an external program has already handled this). Create all file structures in the next conversation turn before providing the files",
        "status": "in_progress or completed",
        "askForInput": "Please note that the execution results of the command will always be sent to you. Request additional information from the user or ask for further requirements only when necessary. Whether user input is needed (true/false)"
        }
        If the project requires manual intervention (e.g., front-end code), include 'manual intervention' in the message.
        When the project is complete, set the status to 'completed'."""
}

# 初始化对话历史
conversation_history = [system_message]

# 创建项目文件夹
project_id = str(uuid.uuid4())
project_dir = Path("projects") / project_id
project_dir.mkdir(parents=True, exist_ok=True)
print(f"{fg('yellow')}项目文件夹已创建: {project_dir}{attr('reset')}")

print(f"{fg('blue')}====== CodeCopilot V1 ======{attr('reset')}")
print(f"{fg('green')}Model: {model} {attr('reset')}")
print(f"{fg('green')}Running on {sys.platform} {attr('reset')}")

# 主循环
askForInput = True
while True:
    # 获取模型上一次的响应（如果有）
    # last_assistant_response = conversation_history[-1] if conversation_history[-1]["role"] == "assistant" else None
    
    # if last_assistant_response:
    #     try:
    #         response_json = json.loads(last_assistant_response["content"])
    #         askForInput = response_json.get("askForInput", False)
    #         status = response_json.get("status", "in_progress")
    #     except json.JSONDecodeError:
    #         askForInput = True
    #         status = "in_progress"
    # else:
    #     askForInput = True
    #     status = "in_progress"
    
    # 根据 askForInput 决定是否提示用户输入
    if askForInput:
        user_input = input(f"{fg('green')}请输入您的需求或反馈（输入 'exit' 退出）：{attr('reset')}")
        if user_input.lower() == 'exit':
            print(f"{fg('red')}程序已退出。{attr('reset')}")
            break
    else:
        user_input = ""
    
    # 添加用户输入到对话历史
    if user_input:
        conversation_history.append({"role": "user", "content": user_input})
    
    # 调用 OpenAI API 获取模型响应
    try:
        response = client.chat.completions.create(
            model=model,
            messages=conversation_history,
            temperature=0.7,
            max_tokens=1500
        )
        
        # 获取并解析模型响应
        assistant_response = response.choices[0].message.content
        # print(assistant_response)
        conversation_history.append({"role": "assistant", "content": assistant_response})
        
        response_json = json.loads(assistant_response)
        files = response_json.get("files", [])
        message = response_json.get("message", "")
        run_command = response_json.get("run_command", "")
        status = response_json.get("status", "in_progress")
        askForInput = response_json.get("askForInput", False)
        
        print(f"{fg('blue')}助手: {message}{attr('reset')}")
        
        # 保存生成的文件到项目文件夹
        for file in files:
            filename = file["filename"]
            content = file["content"]
            file_path = project_dir / filename
            file_path.write_text(content)
            print(f"{fg('cyan')}已保存文件: {file_path}{attr('reset')}")
        
        # 自动执行 run_command 并捕获输出
        if run_command:
            print(f"{fg('magenta')}执行命令: {run_command}{attr('reset')}")
            if input(f"{fg('red')}是否执行命令？(y/n): {attr('reset')}").lower() == 'y':
                try:
                    result = subprocess.run(run_command, shell=True, cwd=project_dir, capture_output=True, text=True)
                    if result.returncode == 0:
                        output = result.stdout
                        print(f"{fg('green')}命令执行成功，输出:\n{output}{attr('reset')}")
                    else:
                        output = result.stderr
                        print(f"{fg('red')}命令执行失败，错误:\n{output}{attr('reset')}")
                except Exception as e:
                    output = str(e)
                    print(f"{fg('red')}执行命令时发生错误: {output}{attr('reset')}")
                
                # 将命令输出发回给模型
                conversation_history.append({"role": "user", "content": f"命令执行输出：\n{output}"})
            else:
                conversation_history.append({"role": "system", "content": "用户拒绝了命令执行"})

        
        # 检查是否需要手动干预
        if "manual intervention" in message.lower():
            print(f"{fg('yellow')}提示: 项目需要手动干预，例如调试前端代码。{attr('reset')}")
        
        # 检查项目是否完成
        if status == "completed":
            print(f"{fg('green')}项目已完成。{attr('reset')}")
            break
    
    except json.JSONDecodeError:
        print(f"{fg('red')}助手响应格式错误，请重试。{attr('reset')}")
    except Exception as e:
        print(f"{fg('red')}发生错误: {str(e)}{attr('reset')}")