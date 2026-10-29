"""模型服务的入口：API key 只在 config 里定义，这里转发。"""




def _api_key() -> str:
    """API key 的统一入口在 chaita.config，这里只做转发。"""
    from ... import config
    return config.api_key()
