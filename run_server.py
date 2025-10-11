#!/usr/bin/env python3
"""
Script de lancement pour l'application Tesla MCP.
Usage: python3 run_server.py
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "tesla_mcp.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )