# LocalAI Config Backup

> ⚠️ ไฟล์นี้เก็บ API keys เป็น plaintext — อย่าอัปโหลด/แชร์
> อัปเดตอัตโนมัติทุกครั้งที่แก้ Settings ใน chat.html

อัปเดต: 2026-09-26 08:54:11

## Providers (5 ราย)

### 1. OpenRouter
- **Base URL:** https://openrouter.ai/api/v1
- **API Key:** `sk-or-v1…1029` (full ในบล็อก JSON ด้านล่าง)
- **Models (21):** cohere/north-mini-code:free, dots-studio/dots-3-note-preview:free, google/gemma-4-26b-a4b-it:free, google/gemma-4-31b-it:free, google/lyria-3-clip-preview, google/lyria-3-pro-preview, inclusionai/ling-3.0-flash-fin:free, inclusionai/ling-3.0-flash-sante:free, liquid/lfm-2.5-2.6b:free, nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free, nvidia/nemotron-3-super-120b-a12b:free, nvidia/nemotron-3-ultra-550b-a55b:free, nvidia/nemotron-3.5-content-safety:free, nvidia/nemotron-3.5-lightning:free, openrouter/free, poolside/laguna-s-2.1:free, poolside/laguna-xs-2.1:free, qwen/qwen3.8-27b:free, stealth/space-bunny-alpha, thinkingmachines/inkling-small:free …

### 2. Google Gemini
- **Base URL:** https://generativelanguage.googleapis.com/v1beta/openai
- **API Key:** `AQ.Ab8RN…EHrQ` (full ในบล็อก JSON ด้านล่าง)
- **Models (27):** models/gemini-2.5-flash, models/gemini-2.5-flash-image, models/gemini-2.5-flash-lite, models/gemini-2.5-flash-native-audio-latest, models/gemini-2.5-flash-native-audio-preview-09-2025, models/gemini-2.5-flash-native-audio-preview-12-2025, models/gemini-2.5-flash-preview-tts, models/gemini-3-flash-preview, models/gemini-3.1-flash-image, models/gemini-3.1-flash-image-preview, models/gemini-3.1-flash-lite, models/gemini-3.1-flash-lite-image, models/gemini-3.1-flash-lite-preview, models/gemini-3.1-flash-live-preview, models/gemini-3.1-flash-tts-preview, models/gemini-3.5-flash, models/gemini-3.5-flash-lite, models/gemini-3.6-flash, models/gemini-3.7-flash, models/gemini-3.8-flash …

### 3. OpenAI
- **Base URL:** https://api.openai.com/v1
- **API Key:** `sk-proj-…0jYA` (full ในบล็อก JSON ด้านล่าง)
- **Models (126):** babbage-002, chat-latest, chatgpt-image-latest, davinci-002, gpt-3.5-turbo, gpt-3.5-turbo-0125, gpt-3.5-turbo-1106, gpt-3.5-turbo-16k, gpt-3.5-turbo-instruct, gpt-3.5-turbo-instruct-0914, gpt-4.1, gpt-4.1-2025-04-14, gpt-4.1-mini, gpt-4.1-mini-2025-04-14, gpt-4.1-nano, gpt-4.1-nano-2025-04-14, gpt-4o, gpt-4o-2024-05-13, gpt-4o-2024-08-06, gpt-4o-2024-11-20 …

### 4. กำหนดเอง (OpenAI-compatible)
- **Base URL:** https://api.groq.com/openai/v1
- **API Key:** `gsk_qnjg…OjE6` (full ในบล็อก JSON ด้านล่าง)
- **Models (3):** allam-2-7b, whisper-large-v3, whisper-large-v3-turbo

### 5. Groq (เร็วมาก)
- **Base URL:** https://api.groq.com/openai/v1
- **API Key:** `gsk_td93…lq3B` (full ในบล็อก JSON ด้านล่าง)
- **Models (3):** allam-2-7b, whisper-large-v3, whisper-large-v3-turbo

## Settings

| Key | Value |
|-----|-------|
| system |  |
| ctx | 4096 |
| temp | 0.7 |
| topK | 4 |
| ragOn | False |
| ttsEngine | neural |
| neuralVoice | th-TH-PremwadeeNeural |
| voiceRate | 1 |
| ttsUrl | http://127.0.0.1:11435 |
| freeOnline | True |
| autoFallback | True |

## Raw JSON (ระบบใช้บล็อกนี้ตอน restore)

```json
{
  "apiUrl": "http://localhost:11434",
  "system": "",
  "temp": 0.7,
  "ctx": 4096,
  "model": "",
  "ragOn": false,
  "embModel": "bge-m3",
  "kbServer": "http://localhost:5002",
  "autoBackup": true,
  "topK": 4,
  "freeOnline": true,
  "autoFallback": true,
  "providers": [
    {
      "id": "pmu6v13yrvrg73",
      "label": "OpenRouter",
      "type": "openai",
      "baseUrl": "https://openrouter.ai/api/v1",
      "apiKey": "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",
      "models": [
        "cohere/north-mini-code:free",
        "dots-studio/dots-3-note-preview:free",
        "google/gemma-4-26b-a4b-it:free",
        "google/gemma-4-31b-it:free",
        "google/lyria-3-clip-preview",
        "google/lyria-3-pro-preview",
        "inclusionai/ling-3.0-flash-fin:free",
        "inclusionai/ling-3.0-flash-sante:free",
        "liquid/lfm-2.5-2.6b:free",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "nvidia/nemotron-3.5-content-safety:free",
        "nvidia/nemotron-3.5-lightning:free",
        "openrouter/free",
        "poolside/laguna-s-2.1:free",
        "poolside/laguna-xs-2.1:free",
        "qwen/qwen3.8-27b:free",
        "stealth/space-bunny-alpha",
        "thinkingmachines/inkling-small:free",
        "thinkingmachines/inkling:free"
      ]
    },
    {
      "id": "pmu6v3ppagkjzx",
      "label": "Google Gemini",
      "type": "openai",
      "baseUrl": "https://generativelanguage.googleapis.com/v1beta/openai",
      "apiKey": "AQ.Ab8RN6JJLzFq849UY11OQIJHz2HDlHkhonOcJJ4zLv2g-WEHrQ",
      "models": [
        "models/gemini-2.5-flash",
        "models/gemini-2.5-flash-image",
        "models/gemini-2.5-flash-lite",
        "models/gemini-2.5-flash-native-audio-latest",
        "models/gemini-2.5-flash-native-audio-preview-09-2025",
        "models/gemini-2.5-flash-native-audio-preview-12-2025",
        "models/gemini-2.5-flash-preview-tts",
        "models/gemini-3-flash-preview",
        "models/gemini-3.1-flash-image",
        "models/gemini-3.1-flash-image-preview",
        "models/gemini-3.1-flash-lite",
        "models/gemini-3.1-flash-lite-image",
        "models/gemini-3.1-flash-lite-preview",
        "models/gemini-3.1-flash-live-preview",
        "models/gemini-3.1-flash-tts-preview",
        "models/gemini-3.5-flash",
        "models/gemini-3.5-flash-lite",
        "models/gemini-3.6-flash",
        "models/gemini-3.7-flash",
        "models/gemini-3.8-flash",
        "models/gemini-3.8-flash-lite-tts",
        "models/gemini-3.8-flash-tts",
        "models/gemini-flash-latest",
        "models/gemini-flash-lite-latest",
        "models/gemini-omni-1.1-flash",
        "models/gemini-omni-flash-preview",
        "models/lyria-realtime-exp"
      ]
    },
    {
      "id": "pmu6v5gv8u8coq",
      "label": "OpenAI",
      "type": "openai",
      "baseUrl": "https://api.openai.com/v1",
      "apiKey": "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",
      "models": [
        "babbage-002",
        "chat-latest",
        "chatgpt-image-latest",
        "davinci-002",
        "gpt-3.5-turbo",
        "gpt-3.5-turbo-0125",
        "gpt-3.5-turbo-1106",
        "gpt-3.5-turbo-16k",
        "gpt-3.5-turbo-instruct",
        "gpt-3.5-turbo-instruct-0914",
        "gpt-4.1",
        "gpt-4.1-2025-04-14",
        "gpt-4.1-mini",
        "gpt-4.1-mini-2025-04-14",
        "gpt-4.1-nano",
        "gpt-4.1-nano-2025-04-14",
        "gpt-4o",
        "gpt-4o-2024-05-13",
        "gpt-4o-2024-08-06",
        "gpt-4o-2024-11-20",
        "gpt-4o-mini",
        "gpt-4o-mini-2024-07-18",
        "gpt-4o-mini-search-preview",
        "gpt-4o-mini-search-preview-2025-03-11",
        "gpt-4o-mini-transcribe",
        "gpt-4o-mini-transcribe-2025-03-20",
        "gpt-4o-mini-transcribe-2025-12-15",
        "gpt-4o-mini-tts",
        "gpt-4o-mini-tts-2025-03-20",
        "gpt-4o-mini-tts-2025-12-15",
        "gpt-4o-search-preview",
        "gpt-4o-search-preview-2025-03-11",
        "gpt-4o-transcribe",
        "gpt-4o-transcribe-diarize",
        "gpt-5",
        "gpt-5-2025-08-07",
        "gpt-5-chat-latest",
        "gpt-5-codex",
        "gpt-5-mini",
        "gpt-5-mini-2025-08-07",
        "gpt-5-nano",
        "gpt-5-nano-2025-08-07",
        "gpt-5-pro",
        "gpt-5-pro-2025-10-06",
        "gpt-5-search-api",
        "gpt-5-search-api-2025-10-14",
        "gpt-5.1",
        "gpt-5.1-2025-11-13",
        "gpt-5.1-chat-latest",
        "gpt-5.1-codex",
        "gpt-5.1-codex-max",
        "gpt-5.1-codex-mini",
        "gpt-5.2",
        "gpt-5.2-2025-12-11",
        "gpt-5.2-chat-latest",
        "gpt-5.2-codex",
        "gpt-5.2-pro",
        "gpt-5.2-pro-2025-12-11",
        "gpt-5.3-chat-latest",
        "gpt-5.3-codex",
        "gpt-5.4",
        "gpt-5.4-2026-03-05",
        "gpt-5.4-mini",
        "gpt-5.4-mini-2026-03-17",
        "gpt-5.4-nano",
        "gpt-5.4-nano-2026-03-17",
        "gpt-5.4-pro",
        "gpt-5.4-pro-2026-03-05",
        "gpt-5.5",
        "gpt-5.5-2026-04-23",
        "gpt-5.5-pro",
        "gpt-5.5-pro-2026-04-23",
        "gpt-5.6-luna",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-6-astra",
        "gpt-6-luna",
        "gpt-6-sol",
        "gpt-audio",
        "gpt-audio-1.5",
        "gpt-audio-2025-08-28",
        "gpt-audio-mini",
        "gpt-audio-mini-2025-10-06",
        "gpt-audio-mini-2025-12-15",
        "gpt-image-1",
        "gpt-image-1-mini",
        "gpt-image-1.5",
        "gpt-image-2",
        "gpt-image-2-2026-04-21",
        "gpt-image-2.5-flare",
        "gpt-image-2.5-flare-2026-09-08",
        "gpt-image-2.5-sunburst",
        "gpt-image-2.5-sunburst-2026-09-08",
        "gpt-live-1",
        "gpt-live-transcribe",
        "gpt-realtime",
        "gpt-realtime-1.5",
        "gpt-realtime-2",
        "gpt-realtime-2.1",
        "gpt-realtime-2.1-mini",
        "gpt-realtime-2025-08-28",
        "gpt-realtime-mini",
        "gpt-realtime-mini-2025-12-15",
        "gpt-realtime-translate",
        "gpt-realtime-whisper",
        "gpt-transcribe",
        "o1",
        "o1-2024-12-17",
        "o3",
        "o3-2025-04-16",
        "o3-mini",
        "o3-mini-2025-01-31",
        "o4-mini",
        "o4-mini-2025-04-16",
        "omni-moderation-2024-09-26",
        "omni-moderation-latest",
        "sora-2",
        "sora-2-pro",
        "text-embedding-3-large",
        "text-embedding-3-small",
        "text-embedding-ada-002",
        "tts-1",
        "tts-1-1106",
        "tts-1-hd",
        "tts-1-hd-1106",
        "whisper-1"
      ]
    },
    {
      "id": "pmu6vigal9szpu",
      "label": "กำหนดเอง (OpenAI-compatible)",
      "type": "openai",
      "baseUrl": "https://api.groq.com/openai/v1",
      "apiKey": "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",
      "models": [
        "allam-2-7b",
        "whisper-large-v3",
        "whisper-large-v3-turbo"
      ]
    },
    {
      "id": "pmu7xb5lnl4yer",
      "label": "Groq (เร็วมาก)",
      "type": "openai",
      "baseUrl": "https://api.groq.com/openai/v1",
      "apiKey": "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",
      "models": [
        "allam-2-7b",
        "whisper-large-v3",
        "whisper-large-v3-turbo"
      ]
    }
  ],
  "sel": "local::scb10x/typhoon2.5-qwen3-4b:latest",
  "voice": "",
  "voiceRate": 1,
  "ttsEngine": "neural",
  "neuralVoice": "th-TH-PremwadeeNeural",
  "ttsUrl": "http://127.0.0.1:11435"
}
```
