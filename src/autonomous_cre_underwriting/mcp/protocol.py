"""Model Context Protocol (MCP) data contracts and JSON-RPC dispatch interfaces."""

from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from autonomous_cre_underwriting.types.base import generate_uuid


class MCPTool(BaseModel):
    """Specification of an MCP-accessible tool."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="Unique tool identifier")
    description: str = Field(..., min_length=1, description="Tool purpose and behavior")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="JSON Schema for tool arguments"
    )


class MCPRequest(BaseModel):
    """Standard JSON-RPC 2.0 MCP request envelope."""

    model_config = ConfigDict(extra="forbid")

    jsonrpc: str = Field(default="2.0")
    method: str = Field(..., min_length=1, description="Method name, e.g. tools/list or tools/call")
    params: Dict[str, Any] = Field(default_factory=dict, description="Method arguments")
    id: str = Field(default_factory=generate_uuid, description="Request correlation identifier")


class MCPResponse(BaseModel):
    """Standard JSON-RPC 2.0 MCP response envelope."""

    model_config = ConfigDict(extra="forbid")

    jsonrpc: str = Field(default="2.0")
    result: Optional[Any] = Field(default=None, description="Successful call payload")
    error: Optional[Dict[str, Any]] = Field(default=None, description="Error detail if failed")
    id: str = Field(..., description="Correlating request identifier")


class MCPServerBase:
    """Base dispatch handler for Model Context Protocol servers."""

    def __init__(self, server_name: str, server_version: str = "1.0.0") -> None:
        self.server_name = server_name
        self.server_version = server_version
        self._tools: Dict[str, MCPTool] = {}
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}

    def register_tool(self, tool: MCPTool, handler: Callable[[Dict[str, Any]], Any]) -> None:
        """Register an executable tool and its callback handler."""
        self._tools[tool.name] = tool
        self._handlers[tool.name] = handler

    def list_tools(self) -> List[MCPTool]:
        """Return all registered MCP tools."""
        return list(self._tools.values())

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a registered tool by name with arguments."""
        if name not in self._handlers:
            raise KeyError(f"Tool '{name}' is not registered on MCP server '{self.server_name}'")
        handler = self._handlers[name]
        return handler(arguments)

    def handle_request(self, request: MCPRequest) -> MCPResponse:
        """Process incoming JSON-RPC MCP request and return structured response."""
        try:
            if request.method == "tools/list":
                tools_data = [t.model_dump() for t in self.list_tools()]
                return MCPResponse(id=request.id, result={"tools": tools_data})
            elif request.method == "tools/call":
                tool_name = request.params.get("name", "")
                arguments = request.params.get("arguments", {})
                res = self.call_tool(tool_name, arguments)
                return MCPResponse(id=request.id, result=res)
            elif request.method == "ping":
                return MCPResponse(
                    id=request.id,
                    result={
                        "server": self.server_name,
                        "version": self.server_version,
                        "status": "ok",
                    },
                )
            else:
                return MCPResponse(
                    id=request.id,
                    error={"code": -32601, "message": f"Method '{request.method}' not found"},
                )
        except Exception as exc:
            return MCPResponse(
                id=request.id,
                error={"code": -32000, "message": str(exc)},
            )
