from mcp.server.fastmcp import FastMCP
import requests

mcp = FastMCP("burp-codex")


BURP_URL = "http://127.0.0.1:9876"


@mcp.tool()
def burp_test():
    """
    Test Codex MCP connection.
    """
    return "Codex MCP bridge OK"


@mcp.tool()
def burp_status():
    """
    Check Burp MCP server status.
    """
    try:
        r = requests.get(
            BURP_URL,
            timeout=5,
            stream=True
        )

        return f"Burp MCP reachable, HTTP {r.status_code}"

    except Exception as e:
        return f"Burp MCP error: {e}"


if __name__ == "__main__":
    mcp.run(
        transport="stdio"
    )