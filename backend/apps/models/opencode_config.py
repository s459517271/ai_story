"""opencode 配置文件同步服务。"""

import json
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from django.conf import settings
from django.utils.text import slugify

from .models import ModelProvider


class OpencodeConfigSyncService:
    """将 Django 模型管理中的 LLM 提供商导出到 opencode 配置文件。"""

    schema_url = 'https://opencode.ai/config.json'

    @classmethod
    def is_enabled(cls):
        return bool(getattr(settings, 'OPENCODE_CONFIG_FILE', '').strip())

    @classmethod
    def get_config_path(cls):
        config_path = (getattr(settings, 'OPENCODE_CONFIG_FILE', '') or '').strip()
        return Path(config_path) if config_path else None

    @classmethod
    def get_provider_prefix(cls):
        prefix = (getattr(settings, 'OPENCODE_MANAGED_PROVIDER_PREFIX', '') or 'django').strip()
        return prefix or 'django'

    @classmethod
    def get_default_npm(cls):
        default_npm = (getattr(settings, 'OPENCODE_DEFAULT_PROVIDER_NPM', '') or '@ai-sdk/openai-compatible').strip()
        return default_npm or '@ai-sdk/openai-compatible'

    @classmethod
    def is_supported_provider(cls, provider):
        extra_config = provider.extra_config or {}
        if extra_config.get('is_mock'):
            return False
        executor_class = (provider.executor_class or '').strip().lower()
        if 'mock_llm_client' in executor_class:
            return False
        return provider.provider_type == 'llm' and provider.is_active

    @classmethod
    def build_provider_id(cls, provider):
        extra_config = provider.extra_config or {}
        configured_id = str(extra_config.get('opencode_provider_id') or '').strip()
        if configured_id:
            return configured_id

        slug = slugify(provider.name) or 'provider'
        return f'{cls.get_provider_prefix()}-{slug}-{str(provider.id)[:8]}'

    @classmethod
    def build_provider_name(cls, provider):
        extra_config = provider.extra_config or {}
        configured_name = str(extra_config.get('opencode_provider_name') or '').strip()
        return configured_name or provider.name

    @classmethod
    def build_provider_npm(cls, provider):
        extra_config = provider.extra_config or {}
        configured_npm = str(extra_config.get('opencode_npm') or '').strip()
        return configured_npm or cls.get_default_npm()

    @classmethod
    def normalize_provider_base_url(cls, provider, npm_package):
        raw_url = (provider.api_url or '').strip()
        if not raw_url:
            return raw_url

        if npm_package not in {'@ai-sdk/openai-compatible', '@ai-sdk/openai'}:
            return raw_url

        parsed = urlparse(raw_url)
        path = (parsed.path or '').rstrip('/')
        suffixes = (
            '/chat/completions',
            '/responses',
            '/completions',
            '/embeddings',
            '/images/generations',
            '/images/edits',
            '/audio/speech',
            '/audio/transcriptions',
        )
        for suffix in suffixes:
            if path.endswith(suffix):
                path = path[:-len(suffix)]
                break

        normalized_path = path.rstrip('/') or ''
        return urlunparse((
            parsed.scheme,
            parsed.netloc,
            normalized_path,
            '',
            '',
            '',
        ))

    @classmethod
    def build_model_entry(cls, provider):
        extra_config = provider.extra_config or {}
        context_limit = extra_config.get('opencode_context_limit') or extra_config.get('context_limit') or provider.max_tokens
        model_entry = {
            'name': provider.model_name,
            'limit': {
                'context': 409600,
                # 'context': int(context_limit or provider.max_tokens or 0),
                'output': 128000,
                # 'output': int(provider.max_tokens or 0),
            },
        }

        return model_entry

    @classmethod
    def build_provider_entry(cls, provider):
        provider_id = cls.build_provider_id(provider)
        npm_package = cls.build_provider_npm(provider)
        return provider_id, {
            'name': cls.build_provider_name(provider),
            'npm': npm_package,
            'models': {
                provider.model_name: cls.build_model_entry(provider),
            },
            'options': {
                'baseURL': cls.normalize_provider_base_url(provider, npm_package),
                'apiKey': provider.api_key,
            },
        }

    @classmethod
    def build_runtime_target(cls, provider):
        extra_config = provider.extra_config or {}
        return {
            'provider_id': cls.build_provider_id(provider),
            'model_id': provider.model_name,
            'variant': str(extra_config.get('opencode_variant') or '').strip(),
        }

    @classmethod
    def load_config(cls, path):
        if not path.exists():
            return {
                '$schema': cls.schema_url,
            }

        raw_text = path.read_text(encoding='utf-8').strip()
        if not raw_text:
            return {
                '$schema': cls.schema_url,
            }

        data = json.loads(raw_text)
        if not isinstance(data, dict):
            raise ValueError('opencode 配置文件必须是 JSON 对象')
        data.setdefault('$schema', cls.schema_url)
        return data

    @classmethod
    def write_config(cls, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(f'{path.suffix}.tmp')
        temp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        temp_path.replace(path)

    @classmethod
    def sync(cls):
        if not cls.is_enabled():
            return {
                'enabled': False,
                'path': '',
                'provider_count': 0,
                'provider_ids': [],
            }

        path = cls.get_config_path()
        config = cls.load_config(path)
        provider_map = dict(config.get('provider') or {})
        prefix = cls.get_provider_prefix()

        preserved_provider_map = {
            key: value
            for key, value in provider_map.items()
            if not key.startswith(f'{prefix}-')
        }

        managed_provider_map = {}
        llm_providers = ModelProvider.objects.filter(
            provider_type='llm',
            is_active=True,
        ).order_by('-priority', '-created_at')

        for provider in llm_providers:
            if not cls.is_supported_provider(provider):
                continue
            provider_id, provider_entry = cls.build_provider_entry(provider)
            existing_entry = managed_provider_map.get(provider_id)
            if existing_entry:
                same_connection = (
                    existing_entry.get('npm') == provider_entry.get('npm')
                    and (existing_entry.get('options') or {}).get('baseURL') == (provider_entry.get('options') or {}).get('baseURL')
                    and (existing_entry.get('options') or {}).get('apiKey') == (provider_entry.get('options') or {}).get('apiKey')
                )
                if same_connection:
                    existing_entry.setdefault('models', {}).update(provider_entry.get('models') or {})
                    continue
                provider_id = f'{provider_id}-{str(provider.id)[:8]}'

            managed_provider_map[provider_id] = provider_entry

        config['provider'] = {
            **preserved_provider_map,
            **managed_provider_map,
        }
        cls.write_config(path, config)

        return {
            'enabled': True,
            'path': str(path),
            'provider_count': len(managed_provider_map),
            'provider_ids': list(managed_provider_map.keys()),
        }

    @classmethod
    def get_status(cls):
        path = cls.get_config_path()
        if not cls.is_enabled():
            return {
                'enabled': False,
                'path': '',
                'exists': False,
            }

        return {
            'enabled': True,
            'path': str(path),
            'exists': path.exists() if path else False,
            'provider_prefix': cls.get_provider_prefix(),
        }
