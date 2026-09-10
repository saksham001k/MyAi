import unittest
from myai.routing import plan_request


class RoutingTests(unittest.TestCase):
    models = [{'name': 'Qwen3-4B.gguf', 'bytes': 2300}, {'name': 'qwen-coder-1.5b.gguf', 'bytes': 1000}]
    media = {'presets': [{'id': 'sd15', 'kind': 'image', 'ready': True, 'name': 'Stable Diffusion'}]}

    def route(self, prompt, **kw):
        return plan_request(dict(prompt=prompt, **kw), self.models, self.media)

    def test_one_prompt_selects_work_and_installed_model(self):
        self.assertEqual(self.route('Hello, explain gravity')['kind'], 'chat')
        code = self.route('Write a Python function to add numbers')
        self.assertEqual(code['kind'], 'code')
        self.assertEqual(code['model'], 'qwen-coder-1.5b.gguf')
        self.assertEqual(self.route('Research the latest Python release')['kind'], 'research')
        self.assertEqual(self.route('Read https://python.org')['kind'], 'research')
        self.assertEqual(self.route('Create an image of a lake')['preset'], 'sd15')

    def test_describing_images_is_not_generating_them(self):
        self.assertEqual(self.route('Explain how image generation works')['kind'], 'chat')
        self.assertEqual(self.route('How do I create an image?')['kind'], 'chat')
        self.assertEqual(self.route("Don't create an image; explain the idea")['kind'], 'chat')
        self.assertEqual(self.route('Write Python code to create an image')['kind'], 'code')
        self.assertEqual(self.route('Edit the background', has_image=True)['kind'], 'image')
        self.assertEqual(self.route('What does this image show?', has_image=True)['kind'], 'chat')

    def test_project_scope_must_be_supplied(self):
        self.assertTrue(self.route('Fix my project')['needs_project'])
        project = self.route('Fix the bug', project_path='/tmp/example')
        self.assertEqual(project['kind'], 'project')
        self.assertTrue(project['ready'])
        self.assertEqual(project['model'], 'Qwen3-4B.gguf')
        self.assertEqual(self.route('Hello', project_path='/tmp/example')['kind'], 'chat')

    def test_no_silent_media_fallback_or_download(self):
        result = self.route('Generate a video of a lake')
        self.assertFalse(result['ready'])
        self.assertIsNone(result['model'])
        self.assertFalse(plan_request({'prompt': 'Hello'}, [], {})['ready'])

    def test_invalid_input(self):
        for value in ['', None, {}, 'x'*16001]:
            with self.assertRaises(ValueError):
                self.route(value)


if __name__ == '__main__':
    unittest.main()
