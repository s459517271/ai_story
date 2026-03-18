from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.models.models import ModelProvider
from apps.models.services import ModelProviderService


User = get_user_model()


class ModelProviderVendorServiceTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='vendor-user', password='secret123')
        self.client.force_authenticate(self.user)

    @patch('apps.models.services.requests.get')
    def test_discover_vendor_models_returns_filtered_models(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': [
                {'id': 'gpt-4o-mini', 'owned_by': 'openai'},
                {'id': 'tts-1', 'owned_by': 'openai'},
                {'id': 'o1-preview', 'owned_by': 'openai'},
            ]
        }
        mock_get.return_value = mock_response

        result = ModelProviderService.discover_vendor_models('openai', 'llm', 'sk-test')

        self.assertEqual(result['vendor'], 'openai')
        self.assertEqual(result['capability'], 'llm')
        self.assertEqual([item['id'] for item in result['models']], ['gpt-4o-mini', 'o1-preview'])
        self.assertTrue(all(item['is_recommended'] for item in result['models']))

    def test_batch_create_vendor_models_skips_existing(self):
        ModelProvider.objects.create(
            name='OpenAI / gpt-4o-mini',
            provider_type='llm',
            api_url='https://api.openai.com/v1/chat/completions',
            api_key='sk-old',
            model_name='gpt-4o-mini',
            executor_class='core.ai_client.openai_client.OpenAIClient',
        )

        result = ModelProviderService.batch_create_vendor_models({
            'vendor': 'openai',
            'capability': 'llm',
            'api_key': 'sk-test',
            'model_names': ['gpt-4o-mini', 'gpt-4.1-mini'],
            'is_active': True,
            'timeout': 60,
            'max_tokens': 4096,
            'temperature': 0.7,
            'top_p': 1.0,
            'rate_limit_rpm': 60,
            'rate_limit_rpd': 1000,
            'priority': 0,
        })

        self.assertEqual(result['created_count'], 1)
        self.assertEqual(result['skipped_count'], 1)
        self.assertEqual(result['provider_type'], 'llm')
        self.assertTrue(ModelProvider.objects.filter(model_name='gpt-4.1-mini').exists())

    def test_batch_create_vendor_models_supports_volcengine_text2image(self):
        result = ModelProviderService.batch_create_vendor_models({
            'vendor': 'volcengine',
            'capability': 'text2image',
            'api_key': 'sk-test',
            'model_names': ['doubao-seedream-3-0-t2i'],
            'is_active': True,
            'timeout': 60,
            'max_tokens': 4096,
            'temperature': 0.7,
            'top_p': 1.0,
            'rate_limit_rpm': 60,
            'rate_limit_rpd': 1000,
            'priority': 0,
        })

        provider = ModelProvider.objects.get(model_name='doubao-seedream-3-0-t2i')
        self.assertEqual(result['created_count'], 1)
        self.assertEqual(provider.provider_type, 'text2image')
        self.assertEqual(provider.api_url, 'https://ark.cn-beijing.volces.com/api/v3/images/generations')
        self.assertEqual(provider.executor_class, 'core.ai_client.text2image_client.Text2ImageClient')

    def test_batch_create_vendor_models_supports_volcengine_image2video(self):
        result = ModelProviderService.batch_create_vendor_models({
            'vendor': 'volcengine',
            'capability': 'image2video',
            'api_key': 'sk-test',
            'model_names': ['seedance-1-0-lite-i2v'],
            'is_active': True,
            'timeout': 60,
            'max_tokens': 4096,
            'temperature': 0.7,
            'top_p': 1.0,
            'rate_limit_rpm': 60,
            'rate_limit_rpd': 1000,
            'priority': 0,
        })

        provider = ModelProvider.objects.get(model_name='seedance-1-0-lite-i2v')
        self.assertEqual(result['created_count'], 1)
        self.assertEqual(provider.provider_type, 'image2video')
        self.assertEqual(provider.api_url, 'https://ark.cn-beijing.volces.com/api/v3/videos/generations')
        self.assertEqual(provider.executor_class, 'core.ai_client.image2video_client.VideoGeneratorClient')

    def test_batch_create_vendor_models_supports_gemini_multimodal(self):
        image_result = ModelProviderService.batch_create_vendor_models({
            'vendor': 'gemini',
            'capability': 'text2image',
            'api_key': 'sk-test',
            'model_names': ['imagen-3.0-generate-002'],
            'is_active': True,
            'timeout': 60,
            'max_tokens': 4096,
            'temperature': 0.7,
            'top_p': 1.0,
            'rate_limit_rpm': 60,
            'rate_limit_rpd': 1000,
            'priority': 0,
        })
        video_result = ModelProviderService.batch_create_vendor_models({
            'vendor': 'gemini',
            'capability': 'image2video',
            'api_key': 'sk-test',
            'model_names': ['veo-3.0-fast-generate-preview'],
            'is_active': True,
            'timeout': 60,
            'max_tokens': 4096,
            'temperature': 0.7,
            'top_p': 1.0,
            'rate_limit_rpm': 60,
            'rate_limit_rpd': 1000,
            'priority': 0,
        })

        image_provider = ModelProvider.objects.get(model_name='imagen-3.0-generate-002')
        video_provider = ModelProvider.objects.get(model_name='veo-3.0-fast-generate-preview')
        self.assertEqual(image_result['created_count'], 1)
        self.assertEqual(video_result['created_count'], 1)
        self.assertEqual(image_provider.provider_type, 'text2image')
        self.assertEqual(image_provider.executor_class, 'core.ai_client.text2image_client.Text2ImageClient')
        self.assertEqual(video_provider.provider_type, 'image2video')
        self.assertEqual(video_provider.executor_class, 'core.ai_client.image2video_client.VideoGeneratorClient')

    @patch('apps.models.services.requests.get')
    def test_discover_vendor_models_marks_recommended(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': [
                {'id': 'gemini-2.5-pro'},
                {'id': 'gemini-1.0-legacy'},
            ]
        }
        mock_get.return_value = mock_response

        result = ModelProviderService.discover_vendor_models('gemini', 'llm', 'sk-test')

        self.assertEqual(result['models'][0]['id'], 'gemini-2.5-pro')
        self.assertTrue(result['models'][0]['is_recommended'])
        self.assertFalse(result['models'][1]['is_recommended'])


class ModelProviderVendorViewSetTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='vendor-api-user', password='secret123')
        self.client.force_authenticate(self.user)

    def test_builtin_vendors_endpoint_returns_results(self):
        response = self.client.get('/api/v1/models/providers/builtin_vendors/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)
        volcengine = next(item for item in response.data['results'] if item['key'] == 'volcengine')
        capability_keys = [item['key'] for item in volcengine['capabilities']]
        self.assertIn('llm', capability_keys)
        self.assertIn('text2image', capability_keys)
        self.assertIn('image2video', capability_keys)
        vendor_keys = [item['key'] for item in response.data['results']]
        self.assertIn('gemini', vendor_keys)
        self.assertIn('grok', vendor_keys)
        self.assertIn('deepseek', vendor_keys)
        self.assertIn('minimax', vendor_keys)
        gemini = next(item for item in response.data['results'] if item['key'] == 'gemini')
        gemini_capability_keys = [item['key'] for item in gemini['capabilities']]
        self.assertIn('text2image', gemini_capability_keys)
        self.assertIn('image2video', gemini_capability_keys)

    @patch('apps.models.services.requests.get')
    def test_discover_vendor_models_endpoint(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': [
                {'id': 'qwen-plus'},
                {'id': 'wanx-image'},
            ]
        }
        mock_get.return_value = mock_response

        response = self.client.post('/api/v1/models/providers/discover_vendor_models/', {
            'vendor': 'dashscope',
            'capability': 'llm',
            'api_key': 'sk-test',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['capability'], 'llm')
        self.assertEqual([item['id'] for item in response.data['models']], ['qwen-plus'])

    def test_batch_create_vendor_models_endpoint(self):
        response = self.client.post('/api/v1/models/providers/batch_create_vendor_models/', {
            'vendor': 'moonshot',
            'capability': 'llm',
            'api_key': 'sk-test',
            'model_names': ['moonshot-v1-8k'],
            'is_active': True,
            'timeout': 60,
            'max_tokens': 4096,
            'temperature': 0.7,
            'top_p': 1.0,
            'rate_limit_rpm': 60,
            'rate_limit_rpd': 1000,
            'priority': 0,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created_count'], 1)
        self.assertEqual(response.data['capability'], 'llm')
        self.assertTrue(ModelProvider.objects.filter(model_name='moonshot-v1-8k').exists())

    def test_discover_vendor_models_rejects_unsupported_capability(self):
        response = self.client.post('/api/v1/models/providers/discover_vendor_models/', {
            'vendor': 'moonshot',
            'capability': 'image2video',
            'api_key': 'sk-test',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('capability', response.data)
