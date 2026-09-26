# AI Translator App Design for MatePad SE 11

## Overview
This document outlines the design for an AI-powered translation application optimized for the MatePad SE 11 device, featuring:
- Voice command input/output
- Thai-English/English-Thai translation
- Context-aware meaning expansion
- Local execution on Kirin 710A CPU (no GPU acceleration)

## Device Constraints
- **Chipset**: Kirin 710A (Cortex-A73/A53) - CPU only execution
- **GPU**: Mali-G51 - No LLM acceleration available
- **RAM**: 8 GB - Suitable for 1B-3B parameter models
- **Storage**: Limited internal storage, prefer compact models
- **Connectivity**: May be offline, prioritize local processing

## System Architecture

### 1. Voice Input Module
- **Speech-to-Text (STT)**: Use lightweight offline STT model
- **Recommended**: Vosk API with Thai/English models (~50MB each)
- **Alternative**: Google's Speech-to-Text API (requires internet)
- **Wake Word**: Optional "Hey LocalAI" for hands-free activation

### 2. Translation Engine
- **Core Model**: Typhoon2 1B or similar 1B parameter LLM in GGUF format
- **Quantization**: Q4_K_M for balance of size/performance (~0.8-1GB)
- **Language Pair**: Specialized for Thai-English translation
- **Inference**: Llama.cpp or similar CPU-optimized inference engine

### 3. Meaning Expansion Module
- **Context Analysis**: Use same LLM to analyze translation context
- **Additional Features**:
  - Etymology and word origins
  - Usage examples in different contexts
  - Formal/informal variants
  - Cultural notes and idioms
- **Implementation**: Secondary prompt to LLM after initial translation

### 4. Voice Output Module
- **Text-to-Speech (TTS)**: Offline TTS for natural voice output
- **Recommended**: Piper TTS or eSpeak NG with Thai/English voices
- **Alternative**: Google's Text-to-Speech API (requires internet)

### 5. User Interface
- **Minimalist Design**: Large buttons for voice input/output
- **Display**: Translation results with expandable meaning sections
- **Settings**: Model selection, voice preferences, language pairs
- **History**: Saved translations with search capability

## Implementation Workflow

### Phase 1: Core Translation Functionality
1. Install and configure Vosk STT for Thai/English
2. Set up Llama.cpp with Typhoon2 1B Q4_K_M model
3. Implement basic text translation pipeline
4. Add Piper TTS for voice output
5. Create simple UI with voice button and text display

### Phase 2: Voice Command Integration
1. Implement wake word detection (optional)
2. Add continuous listening mode with timeout
3. Handle voice-to-text conversion with error handling
4. Route STT output to translation engine
5. Play translated text via TTS

### Phase 3: Meaning Expansion Features
1. Design secondary prompt for context analysis
2. Implement expand/collapse UI for detailed meanings
3. Add etymology lookup from embedded dictionary
4. Include usage examples from model knowledge
5. Add formal/register switching options

### Phase 4: Optimization and Polish
1. Optimize model loading times (mmap, lazy loading)
2. Implement model caching for frequent phrases
3. Add battery optimization techniques
4. Create offline fallback for all components
5. Test and refine user experience

## Technical Specifications

### Models Required
1. **STT Model**: Vosk-thai (50MB) + Vosk-en-us (50MB)
2. **LLM**: Typhoon2 1B Q4_K_GGUF (800MB-1.2GB)
3. **TTS**: Piper Thai/English voices (100MB combined)
4. **Total**: ~1.0-1.5GB storage requirement

### Performance Expectations
- **STT Processing**: <2 seconds for short phrases
- **Translation**: 3-8 seconds per sentence on Kirin 710A
- **TTS**: <1 second for short outputs
- **Meaning Expansion**: Additional 2-5 seconds
- **Memory Usage**: 1.5-2.5GB RAM during operation

### Dependencies
- Vosk API for speech recognition
- Llama.cpp for LLM inference
- Piper TTS for speech synthesis
- Android NDK for native components
- Gradle build system
- Kotlin/Java for Android app

## File Structure
```
app/
├── src/
│   ├── main/
│   │   ├── java/com/localai/translator/
│   │   │   ├── MainActivity.kt
│   │   │   ├── VoiceInputManager.kt
│   │   │   ├── TranslationEngine.kt
│   │   │   ├── MeaningExpander.kt
│   │   │   ├── VoiceOutputManager.kt
│   │   │   └── UI components...
│   │   ├── res/
│   │   │   ├── layout/
│   │   │   ├── values/
│   │   │   └── raw/ (voice models)
│   │   └── assets/
│   │       ├── models/
│   │       │   ├── vosk-model-thai/
│   │       │   ├── vosk-model-en/
│   │       │   ├── typhoon2-1b-q4_k_m.gguf
│   │       │   └── piper-voices/
│   │       └── tts/
│   └── test/
└── build.gradle
```

## Implementation Notes for Worktree 2

When building this application in worktree 2:
1. Focus on creating APK that can be sideloaded on MatePad SE 11
2. Ensure all AI components are bundled for offline use
3. Test voice recognition accuracy in noisy environments
4. Optimize for battery life (avoid keeping CPU at 100%)
5. Provide clear user feedback during processing
6. Include fallback to online APIs when available and preferred

## Testing Checklist for Worktree 3
- [ ] Voice input recognizes Thai and English accurately
- [ ] Translation produces correct Thai-English pairs
- [ ] Meaning expansion provides useful additional context
- [ ] Voice output is clear and natural sounding
- [ ] App functions completely offline
- [ ] Battery consumption is reasonable (<15% per hour active use)
- [ ] UI is responsive and accessible
- [ ] App handles interruptions (calls, notifications) gracefully

--- 
*Documentation created: September 26, 2026*
*For Worktree 2 (build) reference*