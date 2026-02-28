# ThirdParty

This directory is reserved for vendored dependencies and git submodules.

Rules for this repository:

- external source drops and submodules belong under `ThirdParty/`
- do not mix vendored code into `Plugins/`, `Wrapping/`, or `CMake/`
- each vendored dependency should live in its own subdirectory
- each vendored dependency should document its source, version, and local patches

This repository currently has no third-party submodules checked in.
