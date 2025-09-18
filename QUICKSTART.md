# Pipecat Quickstart with Local AI Services

This quickstart guide will help you set up a voice AI bot using **local** Moonshine STT and Kokoro TTS services, eliminating the need for external API keys for speech processing.

## Prerequisites

- Python 3.12 or later
- macOS, Linux, or Windows with WSL

## Quick Setup (5 minutes)

### 1. Clone the Repository

```bash
git clone https://github.com/robegamesios/pipecat-quickstart.git
cd pipecat-quickstart
```

### 2. Create Virtual Environment

```bash
python3.12 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Copy Required Model Files and Packages

This step copies the updated Kokoro and Moonshine packages that aren't yet in the official release:

```bash
./copy_desktop_files.sh
```

**Note:** You need the `DO_NOT_DELETE_Copy_this_to_the_pipecat-quickstart_project` folder on your Desktop containing the necessary files.

### 5. Configure API Keys

Create a `.env` file with your OpenAI API key (only needed for LLM):

```bash
cp env.example .env
```

Edit `.env` and add:
```
OPENAI_API_KEY=your_openai_api_key_here
```

### 6. Run the Bot

```bash
python bot.py --transport webrtc
```

Open http://localhost:7860 in your browser and click "Connect" to start talking!

## What Makes This Special

🎤 **Local Speech-to-Text**: Uses Moonshine STT (no Deepgram API key needed)  
🔊 **Local Text-to-Speech**: Uses Kokoro TTS (no Cartesia API key needed)  
🧠 **Cloud LLM**: Uses OpenAI for intelligent responses  
⚡ **Fast Setup**: Everything runs locally except the LLM

## Architecture

```
Browser Audio → Moonshine STT → OpenAI LLM → Kokoro TTS → Browser Audio
                (Local)         (Cloud)      (Local)
```

## File Structure

```
pipecat-quickstart/
├── bot.py                    # Main bot application
├── requirements.txt          # Python dependencies
├── copy_desktop_files.sh    # Script to copy model files
├── download_models.sh       # Alternative: download models from web
├── assets/                  # Model files (copied by script)
│   ├── kokoro-v1.0.onnx    # Kokoro TTS model (310MB)
│   └── voices-v1.0.bin     # Voice data (28MB)
└── venv/                   # Virtual environment with updated packages
```

## Troubleshooting

### First Run Takes Time
The initial startup may take ~20 seconds as models load.

### Audio Issues
- Allow microphone access when prompted
- Check that speakers/headphones are working
- Try a different browser if issues persist

### Model Files Missing
If you get errors about missing model files:
```bash
./download_models.sh  # Alternative download method
```

### Import Errors
Make sure you ran the copy script:
```bash
./copy_desktop_files.sh
```

## Features

- ✅ **100% Local Speech Processing** (no cloud APIs for STT/TTS)
- ✅ **Real-time Voice Conversation**
- ✅ **WebRTC Transport** (works in browser)
- ✅ **Voice Activity Detection** (Silero VAD)
- ✅ **Multiple Voice Options** (Kokoro voices)
- ✅ **Fast Response Times** (local processing)
 - ✅ **Tool Calling (OpenAI)** — includes a local `get_current_weather` tool

## Voice Options

You can change the voice in `bot.py`:
```python
voice_id="af_sarah"    # Female voices: af_sarah, af_bella, af_nicole
voice_id="am_adam"     # Male voices: am_adam, am_eric, am_liam
```

## Next Steps

- Modify the system prompt in `bot.py` to change personality
- Add more tools in `modules/tools/` and register them in `bot.py`
- Deploy to production with Docker
- Integrate with your own data sources

## Support

For issues or questions:
- Check the [Pipecat Documentation](https://docs.pipecat.ai/)
- Join the [Pipecat Discord](https://discord.gg/pipecat)
- Open an issue on GitHub

---

🎉 **Enjoy your local voice AI bot!**
