import pytest
from forge.typegen import TypeGenerator

def test_type_conversion_heuristics():
    gen = TypeGenerator([])
    assert gen._python_to_ts_type("str") == "string"
    assert gen._python_to_ts_type("int") == "number"
    assert gen._python_to_ts_type("bool") == "boolean"
    assert gen._python_to_ts_type("dict[str, Any]") == "Record<string, unknown>"
    assert gen._python_to_ts_type("list[str]") == "string[]"
    assert gen._python_to_ts_type("list[int]") == "number[]"
    assert gen._python_to_ts_type("list[dict]") == "any[]"
    assert gen._python_to_ts_type("None") == "void"
    assert gen._python_to_ts_type("<class 'str'>") == "string"

def test_generate_command_signature():
    gen = TypeGenerator([])
    cmd = {
        "name": "fs_read",
        "schema": {
            "args": [
                {"name": "path", "type": "<class 'str'>", "optional": False},
                {"name": "max_size", "type": "int", "optional": True}
            ],
            "return_type": "<class 'str'>"
        }
    }
    sig = gen._generate_command_signature(cmd)
    assert sig == "fs_read(path: string, max_size?: number): Promise<string>;"

def test_generate_void_return():
    gen = TypeGenerator([])
    cmd = {
        "name": "app_exit",
        "schema": {
            "args": [],
            "return_type": "NoneType"
        }
    }
    sig = gen._generate_command_signature(cmd)
    assert sig == "app_exit(): Promise<void>;"

def test_generate_full_interfaces():
    registry = [
        {
            "name": "fs_read",
            "schema": {
                "args": [{"name": "path", "type": "str", "optional": False}],
                "return_type": "str"
            }
        },
        {
            "name": "clipboard_write",
            "schema": {
                "args": [{"name": "text", "type": "str", "optional": False}],
                "return_type": "None"
            }
        },
        {
            "name": "custom_plugin_cmd",
            "schema": {
                "args": [],
                "return_type": "dict"
            }
        }
    ]
    gen = TypeGenerator(registry)
    output = gen.generate()
    
    assert "export interface ForgeFsApi" in output
    assert "  read(path: string): Promise<string>;" in output
    
    assert "export interface ForgeClipboardApi" in output
    assert "  write(text: string): Promise<void>;" in output
    
    assert "  custom_plugin_cmd(): Promise<Record<string, unknown>>;" in output
