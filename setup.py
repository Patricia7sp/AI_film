from setuptools import setup, find_packages

setup(
    name="langgraph_mcp",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "langgraph>=0.1.0",
        "streamlit>=1.29.0",
        "pydantic>=2.5.0",
        "langchain>=0.1.0"
    ],
    package_data={
        "": ["*.txt", "*.json"]
    },
    include_package_data=True,
    python_requires=">=3.8",
    author="Seu Nome",
    author_email="paty7sp@gmail.com",
    description="MCP (Model Context Protocol) para LangGraph",
    license="MIT"
)
