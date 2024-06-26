from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import streamlit as st

import os
 

# 定义gpu的内存水位线
os.environ['PYTORCH_MPS_HIGH_WATERMARK_RATIO'] = '0.0'

# 释放gpu占用的内存
torch.mps.empty_cache()

if torch.backends.mps.is_available():
    if torch.backends.mps.is_built():
        device = torch.device("mps")
elif torch.cuda.is_available():
    device = torch.device("cuda")
else:
    device = torch.device("cpu")

print("available device is : ",device)

# 在侧边栏中创建一个标题和一个链接
with st.sidebar:
    st.markdown("## LLaMA3 LLM")
    "[开源大模型食用指南 self-llm](https://github.com/datawhalechina/self-llm.git)"

# 创建一个标题和一个副标题
st.title("💬 LLaMA3 Chatbot")
st.caption("🚀 A streamlit chatbot powered by Self-LLM")

# 定义模型路径
mode_name_or_path = 'huggingface'

# 定义一个函数，用于获取模型和tokenizer
@st.cache_resource
def get_model():
    # 从预训练的模型中获取tokenizer
    tokenizer = AutoTokenizer.from_pretrained(mode_name_or_path, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    # 从预训练的模型中获取模型，并设置模型参数
    # model = AutoModelForCausalLM.from_pretrained(mode_name_or_path, torch_dtype=torch.bfloat16).cpu()

    # 使用Apple silicon gpu,torch_dtype=torch.float,同时修改config.json里为float
    model = AutoModelForCausalLM.from_pretrained(mode_name_or_path, torch_dtype=torch.float16, device_map=device)

    # model.to(device) 不能放在这里，会导致模型重复load
    # model = model.to(device)
  
    return tokenizer, model

def bulid_input(prompt, history=[]):
    system_format='<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{content}<|eot_id|>'
    user_format='<|start_header_id|>user<|end_header_id|>\n\n{content}<|eot_id|>'
    assistant_format='<|start_header_id|>assistant<|end_header_id|>\n\n{content}<|eot_id|>\n'
    history.append({'role':'user','content':prompt})
    prompt_str = ''
    # 拼接历史对话
    for item in history:
        if item['role']=='user':
            prompt_str+=user_format.format(content=item['content'])
        else:
            prompt_str+=assistant_format.format(content=item['content'])
    return prompt_str + '<|start_header_id|>assistant<|end_header_id|>\n\n'

# 加载LLaMA3的model和tokenizer
tokenizer, model = get_model()

# 在此处调用，不会引起模型的reload
model = model.to(device)

# 如果session_state中没有"messages"，则创建一个包含默认消息的列表
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# 遍历session_state中的所有消息，并显示在聊天界面上
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# 如果用户在聊天输入框中输入了内容，则执行以下操作
if prompt := st.chat_input():
    
    # 在聊天界面上显示用户的输入
    st.chat_message("user").write(prompt)
    
    # 构建输入
    input_str = bulid_input(prompt=prompt, history=st.session_state["messages"])
    # input_ids = tokenizer.encode(input_str, add_special_tokens=False, return_tensors='pt').cpu()
    #使用Apple MPS，pt=pytorch
    input_ids = tokenizer.encode(input_str, add_special_tokens=False, return_tensors='pt').to(device)

    print("开始推理")
    outputs = model.generate(
        input_ids=input_ids, max_new_tokens=512, do_sample=True,
        top_p=0.9, temperature=0.5, repetition_penalty=1.1, eos_token_id=tokenizer.encode('<|eot_id|>')[0]
        )
    outputs = outputs.tolist()[0][len(input_ids[0]):]
    print("输出推理结果")
    response = tokenizer.decode(outputs)
    response = response.strip().replace('<|eot_id|>', "").replace('<|start_header_id|>assistant<|end_header_id|>\n\n', '').strip()

    # 将模型的输出添加到session_state中的messages列表中
    # st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.messages.append({"role": "assistant", "content": response})
    # 在聊天界面上显示模型的输出
    st.chat_message("assistant").write(response)
    print(st.session_state)

    #推理结束，尝试清理内存，但貌似没有起作用
    torch.mps.empty_cache()