import unittest
from scripts.setup_models import diffusion_asset


class DiffusionSetupTests(unittest.TestCase):
    def asset(self, name, digest='sha256:' + 'a' * 64):
        return {'name': name, 'digest': digest}

    def test_windows_uses_cpu_and_requires_checksum(self):
        cpu = self.asset('sd-master-example-bin-win-cpu-x64.zip')
        releases = [{'assets': [self.asset('sd-bin-win-cuda12-x64.zip'),
                                self.asset(cpu['name'], ''), cpu]}]
        self.assertEqual(diffusion_asset(releases, windows=True), cpu)

    def test_mac_selection_and_draft_filter(self):
        mac = self.asset('sd-bin-Darwin-macOS-arm64.zip')
        self.assertEqual(diffusion_asset([{'assets': [mac]}]), mac)
        with self.assertRaises(ValueError):
            diffusion_asset([{'draft': True, 'assets': [mac]}])

    def test_unverified_and_wrong_architecture_fail(self):
        for name, digest in [('sd-bin-win-cpu-arm64.zip', 'sha256:' + 'a' * 64),
                             ('sd-bin-win-cpu-x64.zip', 'sha256:invalid')]:
            with self.assertRaises(ValueError):
                diffusion_asset([{'assets': [self.asset(name, digest)]}], windows=True)
