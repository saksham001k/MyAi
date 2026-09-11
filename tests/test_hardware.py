import unittest
from unittest.mock import patch

from myai.hardware import detect_hardware, memory_snapshot


class HardwareDetectionTests(unittest.TestCase):
    @patch("myai.hardware.platform.machine", return_value="arm64")
    @patch("myai.hardware.platform.system", return_value="Darwin")
    @patch("myai.hardware.os.cpu_count", return_value=8)
    def test_apple_silicon_uses_metal(self, *_):
        self.assertEqual(detect_hardware(), ("metal", 999, 7))

    @patch("myai.hardware._command_output", return_value="8192")
    @patch("myai.hardware.which", return_value="/usr/bin/nvidia-smi")
    @patch("myai.hardware.platform.machine", return_value="x86_64")
    @patch("myai.hardware.platform.system", return_value="Linux")
    @patch("myai.hardware.os.cpu_count", return_value=12)
    def test_nvidia_vram_sets_cuda_layers(self, *_):
        self.assertEqual(detect_hardware(), ("cuda", 32, 11))

    @patch("myai.hardware.which", return_value=None)
    @patch("myai.hardware.platform.machine", return_value="x86_64")
    @patch("myai.hardware.platform.system", return_value="Linux")
    @patch("myai.hardware.os.cpu_count", return_value=4)
    def test_unknown_host_falls_back_to_cpu(self, *_):
        self.assertEqual(detect_hardware(), ("cpu", 0, 4))

    def test_linux_meminfo_parsing(self):
        sample = "MemTotal:        16384000 kB\nMemAvailable:     8192000 kB\n"
        with patch("myai.hardware.platform.system", return_value="Linux"), \
             patch("myai.hardware._nvidia_vram_mb", return_value=0), \
             patch("myai.hardware._read_meminfo", return_value=sample):
            info = memory_snapshot()
        self.assertEqual(info.total_mb, 16000)
        self.assertEqual(info.available_mb, 8000)
        self.assertEqual(info.source, "/proc/meminfo")


if __name__ == "__main__":
    unittest.main()
