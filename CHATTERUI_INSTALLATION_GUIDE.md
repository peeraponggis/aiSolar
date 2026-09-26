# ChatterUI + Typhoon2 1B Installation Guide for MatePad SE 11

## Device Specifications
- **Chipset**: Kirin 710A (Cortex-A73/A53) - CPU only execution
- **GPU**: Mali-G51 - No LLM acceleration
- **RAM**: 8 GB - Suitable for 1B-3B models
- **App Store**: No Google Play - Requires APK installation via AppGallery or sideload

## Installation Steps

### 1. Enable Unknown Sources Installation
- Go to **Settings** > **Security** > **Install unknown apps**
- Select the browser you'll use for downloading (e.g., Chrome, Firefox)
- Toggle on **"Allow from this source"**

### 2. Download ChatterUI APK
- Open browser on MatePad SE 11
- Navigate to GitHub ChatterUI releases page
- Download the latest `.apk` file for `arm64-v8a` architecture
- Alternative: Check AppGallery for official version if available

### 3. Install ChatterUI
- Locate downloaded APK file in Downloads folder
- Tap on the APK file to begin installation
- Follow on-screen prompts to complete installation
- Launch ChatterUI after installation

### 4. Configure ChatterUI for Local Mode
- Open ChatterUI application
- Navigate to settings/menu
- Select **Local mode** (not Remote/API mode)
- This ensures model runs locally on device without external API calls

### 5. Download Typhoon2 1B Model
- Within ChatterUI app, look for **Import/Download Model** button
- Tap to open model download interface
- Search for "typhoon2 1b gguf" on Hugging Face Hub
- Filter results to find GGUF format models
- Select file ending with `q4_k_m.gguf` (approximately 0.8-1 GB)
- Confirm download and wait for completion

### 6. Load Model into Chat
- After download completes, locate the model in your model library
- Tap **Load** button to load the model into memory
- Wait for initialization (may take 10-30 seconds depending on device)
- Status indicator should show model is ready

### 7. Test the Installation
- Tap on chat interface to begin conversation
- Type test message: **"สวัสดี ช่วยสรุปข่าวสั้นๆ ให้หน่อย"**
- Wait for model to process and generate response
- Evaluate response quality and speed

## Expected Results
- Successful installation of ChatterUI without errors
- Model download completes within reasonable time (depending on internet speed)
- Model loads successfully within 30 seconds on Kirin 710A
- Test query generates coherent Thai language response
- Response time for simple queries should be acceptable (< 10 seconds per token)

## Troubleshooting Tips
- If installation fails: Ensure "Unknown sources" is properly enabled
- If download fails: Check internet connection and available storage
- If model fails to load: Verify sufficient RAM is available (close other apps)
- If performance is slow: Expect CPU-only performance on Kirin 710A
- If app crashes: Clear app cache/data and retry

## Notes for Worktree 2 (Build)
This documentation should be used as reference for:
1. Creating automated installation scripts if needed
2. Testing compatibility with Android build processes
3. Documenting device-specific limitations for development team
4. Preparing fallback options for devices without Google Play

---
*Documentation created: September 26, 2026*
*For Worktree 2 (build) reference*