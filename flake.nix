{
  description = "ComfyUI frontend static assets packaged for Python distribution";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    flake-lib = {
      url = "github:jgus/flake-lib/v1";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.flake-utils.follows = "flake-utils";
    };
  };

  outputs = { self, nixpkgs, flake-utils, flake-lib }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pin = import ./pin.nix;
        inherit (pin) version hash;
        pkgs = import nixpkgs { inherit system; };
        source = { type = "pypi"; pname = "comfyui_frontend_package"; format = "sdist"; };
        comfyui-frontend-package = pkgs.python3Packages.buildPythonPackage {
          pname = "comfyui-frontend-package";
          inherit version;

          pyproject = true;
          src = pkgs.python3Packages.fetchPypi {
            pname = "comfyui_frontend_package";
            inherit version hash;
          };
          build-system = [ pkgs.python3Packages.setuptools ];

          # Upstream's setup.py reads version from $COMFYUI_FRONTEND_VERSION and falls back to "0.1.0" when unset — the sdist builds as 0.1.0 by default. ComfyUI checks the installed dist version against its required floor at startup and emits a noisy warning when it sees 0.1.0. Plumb the real version through.
          env.COMFYUI_FRONTEND_VERSION = version;

          # Rewrite the bundled missingModelDownload-*.js so the existing "Download" button calls our /api/wmi/download endpoint (registered by the in-tree comfyui-web-model-installer custom node) instead of doing a browser `<a href={url} download>` to the user's Downloads folder. Upstream's button is `isDesktop`-hardcoded — there's no runtime knob. Patcher is idempotent and soft-fails (logs + exit 0) on missing file / signature change so a frontend bump doesn't break the build; if the patch ever stops applying the symptom is that the button reverts to the browser-download path, not a build failure.
          postPatch = ''
            ${pkgs.lib.getExe' pkgs.python3 "python3"} ${./patch-download-model.py}
          '';

          doCheck = false;
        };
      in
      {
        packages = {
          "comfyui-frontend-package" = comfyui-frontend-package;
          default = comfyui-frontend-package;
          update-version = flake-lib.lib.mkUpdateVersion {
            inherit pkgs source;
            buildAttr = "comfyui-frontend-package";
          };
          update-branches = flake-lib.lib.mkUpdateBranches {
            inherit pkgs source;
            pinSchema = "pypi";
          };
        };
      });
}
