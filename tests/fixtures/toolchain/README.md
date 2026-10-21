# Real-toolchain samples

One project per language that builds and tests with its real tools. The `toolchain` tier
(`tests/e2e/capabilities/workflows/test_implement_with_real_toolchains_e2e.py`) copies one to a
temporary folder and runs `sw implement` on it with a doubled model. Each holds a build file and no
code: the run writes `greeter`.
