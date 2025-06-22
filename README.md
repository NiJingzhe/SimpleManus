# CAD Agent

A professional AI-powered CAD modeling assistant that helps users create 3D models using CADQuery and PythonOCC frameworks. The agent can understand natural language descriptions of 3D objects and generate executable CAD code.

## 🚀 Features

- **Natural Language CAD Modeling**: Describe your 3D model in plain English, and the agent will generate precise CAD code
- **Multi-Framework Support**: Supports both CADQuery and PythonOCC for different modeling needs
- **Interactive Development**: Real-time code generation, execution, and debugging
- **Intelligent Query Expansion**: Automatically expands vague requirements into detailed modeling specifications
- **File Management**: Built-in file operations for saving and managing generated models
- **Error Handling & Auto-Fix**: Automatically detects and fixes common CAD modeling errors

## 🏗️ Architecture

The project follows a modular architecture:

```
CAD-Agent/
├── agent/
│   └── BaseAgent.py          # Core agent logic with LLM integration
├── config/
│   ├── config.py            # Configuration management
│   └── provider_template.json # LLM provider templates
├── tools/
│   └── tools.py             # CAD tools and utilities
├── main.py                  # Entry point and CLI interface
└── README.md               # This file
```

### Core Components

1. **BaseAgent**: The main AI agent that orchestrates the entire workflow
2. **Tools**: Specialized functions for CAD code generation, file operations, and command execution
3. **Config**: Manages LLM provider configurations and API keys
4. **CLI Interface**: Rich terminal interface for user interaction

## 📋 Prerequisites

### System Requirements

- Python 3.10 or higher
- macOS/Linux (Darwin machine recommended)
- Terminal with Unicode support

### Required Python Packages

This project uses [uv](https://github.com/astral-sh/uv) for fast and reliable dependency management.  
To install all dependencies, run:

```bash
uv sync
```

## ⚙️ Configuration

1. Edit `config/providers.json` with your actual API keys:

```json
{
  "volc_engine": [
    {
      "model_name": "deepseek-v3-250324",
      "api_keys": ["your_actual_api_key_here"],
      "base_url": "https://ark.cn-beijing.volces.com/api/v3/",
      "max_retries": 3,
      "retry_delay": 1
    }
  ],
  "chatanywhere": [
    {
      "model_name": "claude-sonnet-4-20250514",
      "api_keys": ["your_actual_api_key_here"],
      "base_url": "https://api.chatanywhere.tech"
    }
  ]
}
```

2. The agent uses different LLM interfaces for different tasks:

- **BASIC_INTERFACE**: General conversation and coordination
- **CODE_INTERFACE**: CAD code generation (requires more capable model)
- **QUICK_INTERFACE**: Query expansion and simple tasks

## 🚀 Getting Started

### Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd CAD-Agent
```

2. Install dependencies:

```bash
pip install -r requirements.txt  # Create this file based on prerequisites
```

3. Configure your LLM providers (see Configuration section above)

### Running the Agent

Start the interactive CAD agent:

```bash
python main.py
```

### Basic Usage Examples

1. **Simple Object Creation**:

   ```
   >>> Create a cube with 50mm sides
   ```

2. **Complex Mechanical Parts**:

   ```
   >>> I need a DN100 PN16 welding flange according to ASME B16.5 standard
   ```

3. **Parametric Models**:

   ```
   >>> Design a gear with 18 teeth, module 2.0, and 20-degree pressure angle
   ```

### Workflow

1. **Query Input**: Describe your CAD model in natural language
2. **Requirement Expansion**: The agent will ask clarifying questions and expand your requirements
3. **Code Generation**: Generates CAD code using CADQuery or PythonOCC
4. **Execution & Export**: Runs the code and exports to STEP format
5. **Error Handling**: Automatically fixes any issues that arise

## 🛠️ Development Guide

### Project Structure Deep Dive

#### `agent/BaseAgent.py`

The core agent that:

- Manages conversation history and memory
- Coordinates tool usage
- Handles streaming responses
- Implements memory management strategies

Key methods:

- `run()`: Main execution method
- `memory_manage()`: Handles conversation history summarization
- `chat_impl()`: Core chat logic with detailed instructions

#### `tools/tools.py`

Contains specialized tools:

- **`cad_query_code_generation`**: Generates CADQuery code
- **`pythonocc_code_generation`**: Generates PythonOCC code  
- **`make_user_query_more_detailed`**: Expands user requirements
- **`execute_command`**: Runs system commands
- **`interactive_terminal`**: Handles interactive processes
- **`file_operations`**: File read/write operations

#### `config/config.py`

Manages:

- LLM provider configurations
- API key management
- Model selection strategies

### Adding New Tools

To add a new CAD tool:

1. Create a new function in `tools/tools.py`:

```python
@tool(
    name="your_tool_name",
    description="What your tool does"
)
def your_tool_function(param1: str, param2: int) -> str:
    """
    Your tool implementation
    """
    # Tool logic here
    return result
```

2. Add it to the toolkit in `main.py`:

```python
toolkit = [
    cad_query_code_generation,
    pythonocc_code_generation,
    make_user_query_more_detailed,
    execute_command,
    interactive_terminal,
    file_operations,
    your_tool_function,  # Add your new tool here
]
```

### Extending LLM Support

To add a new LLM provider:

1. Add provider configuration to `config/providers.json`
2. Update `config/config.py` to handle the new provider
3. Test with different model capabilities

### Customizing Agent Behavior

The agent's behavior is defined in the `chat_impl` method docstring in `BaseAgent.py`. You can modify:

- Response patterns
- Tool usage strategies  
- Error handling approaches
- Memory management policies

## 🧪 Testing

### Manual Testing

```bash
# Test basic functionality
python main.py

# Test code generation
>>> Create a simple cylinder with radius 10mm and height 20mm
```

### Automated Testing

Create test cases for:

- Code generation quality
- Error handling
- File operations
- Tool integration

Example test structure:

```python
def test_cadquery_generation():
    agent = setup_agent()
    result = agent.run("Create a simple cube")
    assert "cadquery" in result.lower()
    assert ".step" in result.lower()
```

## 📁 Output Management

Generated models are saved in organized directories:

```
./project_outputs/
├── DN100_PN16_welding_flange/
│   ├── flange_model.py
│   ├── flange_model.step
│   └── generation_log.txt
├── gear_18_teeth/
│   ├── gear_model.py
│   ├── gear_model.step
│   └── generation_log.txt
```

## 🔧 Troubleshooting

### Common Issues

1. **Import Errors**:

   ```bash
   # Install missing CAD libraries
   conda install -c conda-forge cadquery
   pip install pythonocc-core
   ```

2. **API Key Issues**:
   - Verify your `config/providers.json` file
   - Check API key permissions and quotas
   - Test with a simple model first

3. **CAD Code Execution Errors**:
   - The agent will automatically attempt to fix code issues
   - Check the generated Python files for syntax errors
   - Verify CAD library installations

4. **Memory Issues**:
   - The agent automatically manages conversation history
   - For long sessions, restart if needed
   - Monitor token usage with your LLM provider

### Debug Mode

Enable verbose output by modifying the console settings in `main.py`:

```python
console = Console(stderr=True)  # Enable debug output
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and test thoroughly
4. Submit a pull request with detailed description

### Code Style

- Follow PEP 8 for Python code
- Use type hints where possible
- Add docstrings for all functions
- Test new features before submitting

## 📝 License

[Add your license information here]

## 🆘 Support

For questions and support:

1. Check the troubleshooting section
2. Review existing issues in the repository
3. Create a new issue with detailed error information

## 🔮 Future Roadmap

- [ ] Web interface for browser-based access
- [ ] Integration with more CAD formats (IGES, STL)
- [ ] Advanced parametric modeling capabilities
- [ ] Integration with simulation tools
- [ ] Multi-language support
- [ ] CAD model optimization suggestions
- [ ] Integration with manufacturing databases

---

**Note**: This project is designed for educational and professional CAD modeling assistance. Always verify generated models meet your specific requirements and safety standards.
