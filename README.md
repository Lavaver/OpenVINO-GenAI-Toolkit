# OpenVINO GenAI Toolkit

This repository provides a post-installation utility suite for OpenVINO, facilitating access to and utilization of GenAI models. It includes both a web-based API server and a command-line interface for interacting with local GenAI models using OpenVINO.

## ✨ Features

### Backend API Server
- **FastAPI-based Web Server** with OpenAI-compatible API
- **CORS Support** for cross-origin requests
- **Model Loading** at startup with device auto-selection
- **Health Check Endpoint** for monitoring
- **Support for Multiple Devices** (AUTO/CPU/GPU/NPU)

### Command-line Interface
- **Interactive Console** with real-time streaming output
- **AI Thinking Process Visualization** with timing
- **Markdown Support** for formatted responses
- **Customizable Generation Parameters** (max tokens, temperature, top-p)
- **Keyboard Interrupt Handling** for graceful termination

### Frontend
- **Vue.js Based Frontend** with [wjc7jx/AIchat](https://github.com/wjc7jx/AIchat) Interface

## 🚀 Quick Start

### Prerequisites
- Python 3.10 or later
- OpenVINO GenAI Toolchain
- An OpenVINO-formatted GenAI model

> [!NOTE]
> Download the model via [Hugging Face](https://huggingface.co/models) or other websites that allow GenAI downloads, and format it into OpenVINO IR format using the following command:
> ```bash
> optimum-cli export openvino --model "/path/to/your/model" --weight-format int4 --trust-remote-code --task text-generation-with-past "/path/to/your/exporter_output"
> ```

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/openvino-genai-toolkit.git
   cd openvino-genai-toolkit
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install frontend dependencies** (optional):
   ```bash
   cd frontend
   npm install
   ```

### Usage

#### Backend API Server

Start the server with your OpenVINO model:

```bash
python bootstrap_backend.py /path/to/your/model -d AUTO
```

- **Arguments**:
  - `model_path`: Path to your local OpenVINO format model directory
  - `-d, --device`: Target device (AUTO/CPU/GPU/NPU)
  - `-p, --port`: Server port (default: 8000)

**API Endpoints**:
- `GET /`: API status
- `GET /health`: Health check
- `POST /v1/chat/completions`: OpenAI-compatible chat endpoint

#### Command-line Console

Run the console with your model and prompt:

```bash
python bootstrap_console.py /path/to/your/model "Your question here" -d AUTO -s
```

- **Arguments**:
  - `model_path`: Path to your local OpenVINO format model directory
  - `prompt`: User input question/prompt
  - `-d, --device`: Target device (default: AUTO)
  - `-m, --max-tokens`: Maximum number of tokens to generate (default: 32768)
  - `-t, --temperature`: Generation temperature (0-1, default: 0.7)
  - `-p, --top-p`: Top-P sampling (0-1, default: 0.9)
  - `-s, --stream`: Enable streaming output (recommended)

#### Frontend (Development)

1. **Navigate to the frontend directory**:
```bash
cd frontend
```

2. **Install frontend dependencies**:
```bash
npm install
```

3. **Run the development server**:
```bash
npm run dev
```

## 📁 Project Structure

```
openvino-genai-toolkit/
├── bootstrap_backend.py     # Backend API server
├── bootstrap_console.py     # Command-line interface
├── config.py                # Configuration file
├── requirements.txt         # Python dependencies
├── LICENSE                  # MIT License
└── frontend/                # Web frontend
    ├── index.html           # Frontend entry point
    ├── package.json         # npm dependencies
    └── node_modules/        # npm packages
```

## 🛠️ Dependencies

### Core Dependencies
- `openvino_genai` - OpenVINO GenAI Toolchain
- `fastapi` - Web API framework

### Development Dependencies
- `rich` - Rich text formatting for CLI
- `vue` - Frontend framework
- `element-plus` - UI components

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📞 Support

For issues and feature requests, please create an issue on the GitHub repository.

## 🔗 Resources

- [OpenVINO Documentation](https://docs.openvino.ai/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Vue.js Documentation](https://vuejs.org/)

---

Made with ❤️ using OpenVINO and FastAPI and Vue.js