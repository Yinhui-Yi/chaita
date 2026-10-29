"""配置读取单元测试（`chaita/config.py`）。

真值来自规则：环境变量优先、其次 config.yaml 的 api_key 行、没找到给空串。
文件 I/O 用 fake 替掉（不碰真实磁盘）。
"""

import io

import chaita.config as config


def _yaml(text):
    def _open(*args, **kwargs):
        return io.StringIO(text)
    return _open


def test_api_key_prefers_env(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "  sk-env  ")
    assert config.api_key() == "sk-env"


def test_api_key_reads_yaml_with_double_quotes(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr("builtins.open", _yaml('api_key: "sk-file"\n'))
    assert config.api_key() == "sk-file"


def test_api_key_strips_single_quotes(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr("builtins.open", _yaml("api_key: 'sk-single'\n"))
    assert config.api_key() == "sk-single"


def test_api_key_skips_comments_and_other_keys(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr("builtins.open",
                        _yaml("# 注释\n\nother: v\napi_key: sk-y\n"))
    assert config.api_key() == "sk-y"


def test_api_key_missing_file_is_empty(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    def _raise(*args, **kwargs):
        raise FileNotFoundError
    monkeypatch.setattr("builtins.open", _raise)
    assert config.api_key() == ""


def test_api_key_other_error_is_empty(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    def _raise(*args, **kwargs):
        raise OSError("boom")
    monkeypatch.setattr("builtins.open", _raise)
    assert config.api_key() == ""
