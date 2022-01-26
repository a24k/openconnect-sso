{ sources ? import ./sources.nix
, pkgs ? import <nixpkgs> {
    overlays = [ (import "${sources.poetry2nix}/overlay.nix") ];
  }
}:

let
  pythonPackages = pkgs.python3Packages;

  openconnect-sso = callPackage ./openconnect-sso.nix { inherit (pkgs) python3Packages; };

  shell = pkgs.mkShell {
    buildInputs = with pkgs; [
      # For Makefile
      gawk
      git
      gnumake
      which
      niv # Dependency manager for Nix expressions
      nixpkgs-fmt # To format Nix source files
      poetry # Dependency manager for Python
    ] ++ (
      with pythonPackages; [
        pre-commit # To check coding style during commit
      ]
    ) ++ (
      # only install those dependencies in the shell env which are meant to be
      # visible in the environment after installation of the actual package.
      # Specifying `inputsFrom = [ openconnect-sso ]` introduces weird errors as
      # it brings transitive dependencies into scope.
      openconnect-sso.propagatedBuildInputs
    );
    shellHook = ''
      # Python wheels are ZIP files which cannot contain timestamps prior to
      # 1980
      export SOURCE_DATE_EPOCH=315532800

      echo "Run 'make help' for available commands"
    '';
  };

  niv = if pkgs ? niv then pkgs.nim else pkgs.haskellPackages.niv;
in
{
  inherit openconnect-sso shell;
}
