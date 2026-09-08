from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from core.ai_client.text2image_client import Text2ImageClient


class Text2ImageClientTestCase(SimpleTestCase):
    @patch('core.ai_client.text2image_client.requests.post')
    def test_images_generations_endpoint_includes_image_array(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'created': 123,
            'usage': {},
            'data': [
                {'url': 'https://example.com/generated.png'}
            ],
        }
        mock_post.return_value = mock_response

        client = Text2ImageClient(
            api_url='https://ark.cn-beijing.volces.com/api/v3/images/generations',
            api_key='test-key',
            model_name='doubao-seedream-5-0-250428',
        )

        with patch.object(client, '_localize_image_item', side_effect=lambda item, width, height, timeout: {
            'url': item['url'],
            'width': width,
            'height': height,
        }):
            result = client.generate(
                prompt='请参考图1生成新图',
                image=['data:image/png;base64,ZmFrZV9pbWFnZQ=='],
                width=1024,
                height=1024,
            )

        self.assertTrue(result.success)
        payload = mock_post.call_args.kwargs['json']
        self.assertEqual(payload['prompt'], '请参考图1生成新图')
        self.assertEqual(payload['image'], ['data:image/png;base64,ZmFrZV9pbWFnZQ=='])
        self.assertEqual(result.metadata['input_image_count'], 1)
