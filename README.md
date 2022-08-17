# nipype-interfaces
A spin-off from NiPype 1.0 codebase outsourcing the interfaces and algorithms submodules.

## Roadmap

*Milestone 1*. Create a new python package `nipype-interfaces` that can seamlessly replace all imports from `nipype.interfaces` and `nipype.algorithms`.

*Milestone 2*. Deduplicate efforts by creating shims in nipype and deprecate importing from `nipype.interfaces` and `nipype.algorithms`.

*Milestone 3*. Equip interfaces with isolated execution and caching capabilities:
  - Move the functions generating pickled results and hashfiles into `nipype-interfaces`.
  - Refactor the `BaseInterface` to be aware of these functions (e.g., add a `cache=False` to the signature of `run()`
  - Create a function that "exports" the interface's state (should not be very different from the caching/restart utilities above.
  - Create an installable script that can read the exported file above and run the interface separately (this, effectively, should allow Pydra to operate any old-style interface).

*Milestone 4*. Bring useful interfaces from niworkflows (e.g., the new nibabel submodule).
