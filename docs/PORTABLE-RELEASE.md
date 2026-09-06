Portable application build for Apple Silicon macOS, Windows x64 and Linux x64.

Includes separate packaged apps (Python bundled), pinned/checksummed llama.cpp and stable-diffusion.cpp runtimes, and relative-path launchers using one shared Workspace directory. Windows/Linux use CPU runtime builds; Mac uses the upstream Apple Silicon build. Runtime startup and packaged API/storage startup must pass on all three CI runners before publication.

Models and personal data are not in this download. Use scripts/prepare_pendrive.py from your source checkout to transfer your downloaded models and conversations into a new folder on the drive.

Compatibility is bounded by upstream binaries: Linux runtimes target Ubuntu 24.04-era systems, x64 CPU instruction support matters, and Mac runtimes may require recent macOS. This is not a guarantee for every OS version or restricted computer. No global security settings are changed.

Real image/video inference, speed, memory use, and physical pendrive operation remain unverified. Video-model downloads have been reported complete by the user; successful generation has not been demonstrated. Keep the whole folder together. Shut down before ejecting.
