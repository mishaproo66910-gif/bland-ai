import json
import os

import requests
import streamlit as st

# ====== ВАШИ ДАННЫЕ ДЛЯ ДОНАТОВ ======
BMC_URL = "https://www.buymeacoffee.com/YOUR_USERNAME"
CRYPTO = {
    "BTC": "YOUR_BTC_ADDRESS",
    "ETH (ERC-20)": "YOUR_ETH_ADDRESS",
    "USDT (TRC-20)": "YOUR_USDT_TRC20_ADDRESS",
    "TON": "YOUR_TON_ADDRESS",
}

# ====== ПРОВАЙДЕРЫ (OpenAI-совместимые эндпоинты) ======
PROVIDERS = {
    "Groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        "secret": "GROQ_API_KEY",
        "keys_url": "https://console.groq.com/keys",
    },
    "Gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "models": ["gemini-2.5-flash", "gemini-2.5-flash-lite"],
        "secret": "GEMINI_API_KEY",
        "keys_url": "https://aistudio.google.com/apikey",
    },
}

st.set_page_config(page_title="AI Chat", page_icon="🤖", layout="wide")


def get_secret(name: str) -> str:
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, "")


def stream_chat(url, key, model, messages, temperature, max_tokens):
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        },
        stream=True,
        timeout=120,
    )
    resp.encoding = "utf-8"
    if resp.status_code != 200:
        raise RuntimeError(f"Ошибка API {resp.status_code}: {resp.text[:500]}")
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        choices = chunk.get("choices") or []
        if choices:
            delta = (choices[0].get("delta") or {}).get("content")
            if delta:
                yield delta


if "messages" not in st.session_state:
    st.session_state.messages = []

# ====== БОКОВАЯ ПАНЕЛЬ ======
with st.sidebar:
    st.header("⚙️ Настройки")

    provider = st.selectbox("Провайдер", list(PROVIDERS.keys()))
    cfg = PROVIDERS[provider]

    model_choice = st.selectbox("Модель", cfg["models"] + ["Другая…"])
    model = (
        st.text_input("Название модели", value=cfg["models"][0])
        if model_choice == "Другая…"
        else model_choice
    )

    saved_key = get_secret(cfg["secret"])
    api_key = st.text_input(
        "API-ключ",
        type="password",
        value="",
        placeholder="Взят из Secrets" if saved_key else "Вставьте ключ",
        help="Бесплатный ключ: " + cfg["keys_url"],
    ) or saved_key
    st.markdown(f"[Получить бесплатный ключ]({cfg['keys_url']})")

    system_prompt = st.text_area(
        "Системный промпт",
        value="Ты умный, точный и полезный ассистент. Отвечай на языке пользователя.",
        height=120,
    )
    temperature = st.slider("Температура", 0.0, 2.0, 0.7, 0.05)
    max_tokens = st.slider("Макс. токенов ответа", 128, 8192, 2048, 128)
    history_len = st.slider("Сообщений в контексте", 2, 40, 12, 2)

    if st.button("🗑 Очистить чат", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    if st.session_state.messages:
        export = "\n\n".join(
            f"[{m['role']}]\n{m['content']}" for m in st.session_state.messages
        )
        st.download_button(
            "💾 Скачать диалог",
            export,
            file_name="chat.txt",
            mime="text/plain",
            use_container_width=True,
        )

    st.divider()
    st.subheader("❤️ Поддержать проект")
    st.link_button("☕ Buy Me a Coffee", BMC_URL, use_container_width=True)
    with st.expander("🪙 Crypto"):
        coin = st.selectbox("Монета / сеть", list(CRYPTO.keys()))
        st.code(CRYPTO[coin], language=None)
        st.caption("Нажмите на иконку справа, чтобы скопировать адрес.")

# ====== ЧАТ ======
st.title("🤖 AI Chat")
st.caption(f"{provider} · {model}")

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("Напишите сообщение…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if not api_key:
            st.error("Введите API-ключ в боковой панели.")
        else:
            context = [{"role": "system", "content": system_prompt}] + [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages[-history_len:]
            ]
            try:
                reply = st.write_stream(
                    stream_chat(cfg["url"], api_key, model, context, temperature, max_tokens)
                )
                st.session_state.messages.append({"role": "assistant", "content": reply})
            except Exception as e:
                st.error(str(e))
