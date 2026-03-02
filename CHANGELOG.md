# Changelog

## [0.2.0](https://github.com/failed33/paraview-mcp/compare/ParaViewMCP-v0.1.5...ParaViewMCP-v0.2.0) (2026-03-02)


### ⚠ BREAKING CHANGES

* **plugin:** The dock widget (ParaViewMCPDockWindow) has been removed in favor of the new toolbar popup. Users who had the dock pinned will find the MCP controls in the toolbar instead.

### Features

* migrate from mcp SDK to FastMCP v3 and expand test coverage to 98% ([fa3f30d](https://github.com/failed33/paraview-mcp/commit/fa3f30d482510422e3bca9b479fcc8eb50f94cba))
* **plugin:** add toolbar popup UI with execution history and snapshot restore ([f90c4ed](https://github.com/failed33/paraview-mcp/commit/f90c4eddcdecbe1c32fd82c01057d383f6b0f8fd))
* **plugin:** add toolbar popup UI with execution history and snapshot restore ([d1ff4c7](https://github.com/failed33/paraview-mcp/commit/d1ff4c729aa2ffd3c8b78c4d416d32afcb994b3b))


### Bug Fixes

* add missing _connection null assertion in get_connection edge test ([68529ff](https://github.com/failed33/paraview-mcp/commit/68529fffecef8934d0b5725e35262b0beb4f7925))


### Documentation

* add combined ParaView + MCP logo to README ([76bd334](https://github.com/failed33/paraview-mcp/commit/76bd33493da52af8296aad0f31bd00faca6da86a))
* **server:** regenerate third-party notices for FastMCP v3 ([4828f23](https://github.com/failed33/paraview-mcp/commit/4828f2300a5438b44dd7c73e8297d6e05a60bfa4))

## [0.1.5](https://github.com/failed33/paraview-mcp/compare/ParaViewMCP-v0.1.4...ParaViewMCP-v0.1.5) (2026-03-01)


### Bug Fixes

* regenerate Qt6 QFlags patch and exclude patches from formatting ([5cfe196](https://github.com/failed33/paraview-mcp/commit/5cfe1962b1eda485fddf033d04d3a902be3bd54c))
* use patch instead of git apply for Qt6 QFlags patch and shorten MCP description ([bd04dbe](https://github.com/failed33/paraview-mcp/commit/bd04dbe68a38c706eaf4b20b5093bfd798f00c15))

## [0.1.4](https://github.com/failed33/paraview-mcp/compare/ParaViewMCP-v0.1.3...ParaViewMCP-v0.1.4) (2026-03-01)


### Features

* **ci:** add third-party license notices and CI license validation ([b2e664e](https://github.com/failed33/paraview-mcp/commit/b2e664e1b6d7c69bca956e7e100dace32e8b14de))
* **ci:** auto-generate Python section of THIRD-PARTY-NOTICES.txt ([5bb45e1](https://github.com/failed33/paraview-mcp/commit/5bb45e1cf2bbfe10164879521917a4819f109388))
* prepare server.json for MCP registry publishing ([e01a9e8](https://github.com/failed33/paraview-mcp/commit/e01a9e883301b4ff4ac3a47148497f34f4b9b46a))


### Bug Fixes

* apply Qt 6.9 QFlags compatibility patch for macOS ParaView build ([b0f8be2](https://github.com/failed33/paraview-mcp/commit/b0f8be2cd327e9946970a5fc593df53dbd85e8c7))


### Documentation

* add "Inspired by" section to README ([d96dadd](https://github.com/failed33/paraview-mcp/commit/d96dadd0456e03a4dffadf4deb0da4ed7ef7708c))
* simplify README prerequisites and remove installation instructions for MCP server ([b6fedeb](https://github.com/failed33/paraview-mcp/commit/b6fedebeaad2f23bebe77d56748f3195f5014139))
* update installation instructions for MCP client connection in the packaged instructons ([c324fb9](https://github.com/failed33/paraview-mcp/commit/c324fb975517448bb2c1a9161f5b3c85ae34d58e))
* update README to replace "AI assistants" with "LLM assistants" for clarity ([587a75a](https://github.com/failed33/paraview-mcp/commit/587a75a249a8f1c82d51cea4e7ac2db4f2e54b6d))

## [0.1.3](https://github.com/failed33/paraview-mcp/compare/ParaViewMCP-v0.1.2...ParaViewMCP-v0.1.3) (2026-03-01)


### Features

* **ci:** add workflow_dispatch trigger to CI, Coverage, and CodeQL ([7fa0373](https://github.com/failed33/paraview-mcp/commit/7fa0373a89e69c4117a782e3f22b835b692e2244))
* **ci:** switch from Qt5 to Qt6 across all builds ([bac8a16](https://github.com/failed33/paraview-mcp/commit/bac8a166442bce6ea2dcfdcc85caa90d1a7cba89))


### Bug Fixes

* **ci:** remove unused ThirdParty lcov exclude pattern ([9ec1746](https://github.com/failed33/paraview-mcp/commit/9ec1746653e3d562bb3a69fcc3c4d55fe6d457c9))
* **ci:** update docker/build-push-action to v6.19.2 ([44b590f](https://github.com/failed33/paraview-mcp/commit/44b590f82217fd5da300466c89aee391f35281ba))
* **ci:** use custom CI container for Linux release build ([6d557ba](https://github.com/failed33/paraview-mcp/commit/6d557ba2790e0e0b6cdc08b6a0360cea47932ff2))
* **docker:** add Qt6Core5Compat package for ParaView Qt6 build ([15b0739](https://github.com/failed33/paraview-mcp/commit/15b0739ece1a6308bd12041f2fdcf5e3121f2e72))
* **docker:** add xsltproc for ParaView Qt6 build ([f73464f](https://github.com/failed33/paraview-mcp/commit/f73464f119d020dac6510982e6b66042eee056a8))
* **docker:** bake all build deps into CI image, remove redundant installs ([f32a18b](https://github.com/failed33/paraview-mcp/commit/f32a18bebe535507c1fd358f846ae190dafbb68e))
* **docker:** isolate ParaView build layer and use registry caching ([04e4a99](https://github.com/failed33/paraview-mcp/commit/04e4a9992c919fea868c4329541146adf233cb04))
* **docker:** use correct Qt6 package names for Ubuntu 24.04 ([80ea745](https://github.com/failed33/paraview-mcp/commit/80ea7451906b4f4e4e5feb0d51c40dc8ef7a35a2))

## [0.1.2](https://github.com/failed33/paraview-mcp/compare/ParaViewMCP-v0.1.1...ParaViewMCP-v0.1.2) (2026-02-28)


### Features

* **ci:** add CodeQL security scanning and Codecov coverage ([ff8d44f](https://github.com/failed33/paraview-mcp/commit/ff8d44f53a1ddd450537a0fe057eb7d387210b2a))
* **ci:** add macOS arm64 build and include plugins.xml in release ([079feb4](https://github.com/failed33/paraview-mcp/commit/079feb46002418cbaf93a06145cf986699851f79))
* **ci:** add pre-built Linux plugin binary to GitHub Releases ([d1c6ee6](https://github.com/failed33/paraview-mcp/commit/d1c6ee6fc68cd843951671a75fbfce6b3a453fc7))
* **server:** rename PyPI package to paraview-mcp-server ([5548bcd](https://github.com/failed33/paraview-mcp/commit/5548bcd413ebeb67ca46aa45812fe5f480fb7b7e))


### Bug Fixes

* **ci:** add pypi environment to release workflow for trusted publishing ([8be3bb2](https://github.com/failed33/paraview-mcp/commit/8be3bb2778c5f34dd2ddd8cdd07daa4968f32bd9))
* **ci:** harden CI/CD security and apply code review findings ([8592ad0](https://github.com/failed33/paraview-mcp/commit/8592ad0273b207ead8a5f28e5c492dcbabe1156b))
* **ci:** install git, curl, gpg for Codecov upload in container ([21120f8](https://github.com/failed33/paraview-mcp/commit/21120f86d845acecbe08eca71205e6625e1a77b5))
* **ci:** use GCC coverage flags instead of LLVM in C++ coverage job ([107b9a6](https://github.com/failed33/paraview-mcp/commit/107b9a6eeae19286afbb250a3cf4565cf41cf67f))

## [0.1.1](https://github.com/failed33/paraview-mcp/compare/ParaViewMCP-v0.1.0...ParaViewMCP-v0.1.1) (2026-02-28)


### Features

* add open-source publication scaffolding ([c165ad9](https://github.com/failed33/paraview-mcp/commit/c165ad9180df3e8562c911ed4aa5afdb09c9eae9))


### Bug Fixes

* **ci:** add missing qtxmlpatterns5-dev-tools to Docker image ([4d33d95](https://github.com/failed33/paraview-mcp/commit/4d33d9567cfa5e1b08317bae347ee30d5f156e7f))
* **ci:** add Qt5Help dev package and fix Dockerfile runtime deps ([ba5c1c6](https://github.com/failed33/paraview-mcp/commit/ba5c1c671f3f7d2136c8fb480b589edeaa27b88d))
* **ci:** configure pyrefly search paths for src layout ([a2c9633](https://github.com/failed33/paraview-mcp/commit/a2c9633af25a69509a9063026c044084c34d4114))
* **ci:** fix pyrefly config syntax and ruff E402 in tests ([3934483](https://github.com/failed33/paraview-mcp/commit/39344834e00e866af3a56002d1c5e05076e18635))
* **ci:** fix pyrefly missing-import errors and install dev dependencies ([2939df8](https://github.com/failed33/paraview-mcp/commit/2939df8f3f5447b5664c3e46a9e9b23aac1f64cf))
* **ci:** install CMake 3.24+ in cpp job via pip ([a57b4b0](https://github.com/failed33/paraview-mcp/commit/a57b4b0337642bf4315ea9be8ce25f320edaced4))
* **ci:** install python3-pip before cmake in cpp container ([3e5da3a](https://github.com/failed33/paraview-mcp/commit/3e5da3aefd77afac6479a80c82a72602aef0f08a))
* **ci:** use Qt offscreen platform for headless C++ tests ([9cb1240](https://github.com/failed33/paraview-mcp/commit/9cb12407e53f1f6e24c1e171f26ac5de4d8838fb))
* **plugin:** handle fast server-close in test socket helper ([6f631b2](https://github.com/failed33/paraview-mcp/commit/6f631b29b7ed8a715254d8f9487a33ea573689bb))
* **plugin:** increase test socket timeout for CI containers ([bd903ea](https://github.com/failed33/paraview-mcp/commit/bd903ea77bbd2a5e840e3baef4e6dd1e1fb67015))
* **server:** add ruff src path for first-party import detection in CI ([6e6648e](https://github.com/failed33/paraview-mcp/commit/6e6648effbe03f29d4066d35c015148f0e5db704))
* **server:** replace global E402 ignore with inline noqa on 5 specific lines ([7ad9fa2](https://github.com/failed33/paraview-mcp/commit/7ad9fa2380601c487f370bcc48ba16652dbaa478))
